import logging
import threading
import json

class RoomManager:
    def __init__(self, rooms_file):
        self.rooms_file = rooms_file
        self.lock = threading.RLock()
        self.rooms = []
        self.load_rooms()

    def load_rooms(self):
        with self.lock:
            try:
                with open(self.rooms_file, 'r') as f:
                    self.rooms = json.load(f)
                logging.info("Rooms loaded successfully.")
                self._identify_mob_templates()
            except FileNotFoundError:
                logging.error(f"Rooms file '{self.rooms_file}' not found. Initializing empty rooms list.")
                self.rooms = []
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error while loading rooms: {e}")
                self.rooms = []
            except Exception as e:
                logging.error(f"Failed to load rooms: {e}")
                self.rooms = []

    def save_rooms(self):
        with self.lock:
            try:
                with open(self.rooms_file, 'w') as f:
                    json.dump(self.rooms, f, indent=4)
                logging.info("Rooms saved successfully.")
            except Exception as e:
                logging.error(f"Failed to save rooms: {e}")

    def get_room(self, vnum):
        """
        Retrieve a room by its vnum with proper error handling and field normalization.
        """
        with self.lock:
            try:
                if vnum is None:
                    logging.error("Attempted to get room with None vnum")
                    return None
                    
                # Convert vnum to string for consistent comparison
                str_vnum = str(vnum)
                for room in self.rooms:
                    if not isinstance(room, dict):
                        logging.error(f"Invalid room format found: {room}")
                        continue
                        
                    room_vnum = str(room.get('vnum', ''))
                    if room_vnum == str_vnum:
                        # Normalize room fields
                        normalized_room = {
                            'vnum': room_vnum,
                            'name': room.get('name', 'Unnamed Room'),
                            'description': room.get('description') or room.get('long_desc', 'No description available.'),
                            'exits': {},
                            'mobs': [],
                            'items': [],
                            'players': []
                        }
                        
                        # Normalize exits - handle both uppercase and lowercase keys
                        raw_exits = room.get('exits', {})
                        if isinstance(raw_exits, dict):
                            for direction, target in raw_exits.items():
                                if isinstance(target, str) and target.strip():
                                    normalized_room['exits'][direction.lower()] = target.strip()
                        
                        # Copy over other fields
                        normalized_room['mobs'] = room.get('mobs', [])
                        normalized_room['items'] = room.get('items', [])
                        normalized_room['players'] = room.get('players', [])
                        
                        logging.debug(f"Retrieved and normalized room '{normalized_room['name']}' with vnum {vnum}")
                        return normalized_room
                        
                logging.error(f"Room with vnum {vnum} not found.")
                return None
                
            except Exception as e:
                logging.error(f"Error retrieving room {vnum}: {e}")
                return None

    def _identify_mob_templates(self):
        """Identifies mob templates in each room to avoid treating them as instances."""
        for room in self.rooms:
            for mob in room.get("mobs", []):
                if mob.get("quantity") is not None and mob.get("max_instances") is not None:
                    mob["is_template"] = True
                    logging.info(f"Marked mob {mob.get('vnum')} in room {room.get('vnum')} as a template.")

    def get_rooms_with_mobs(self):
        """Retrieve rooms that contain mobs, skipping templates."""
        with self.lock:
            rooms_with_mobs = {}
            for room in self.rooms:
                mobs = [mob for mob in room.get("mobs", []) if not mob.get("is_template", False)]
                if mobs:
                    rooms_with_mobs[room.get("vnum")] = mobs
            return rooms_with_mobs

    def add_item_to_room(self, room_vnum, item_entry):
        with self.lock:
            room = self.get_room(room_vnum)
            if room:
                if not isinstance(item_entry, dict):
                    logging.error(f"Item entry is not a valid dictionary: {item_entry}")
                    return False
                if 'name' not in item_entry or 'vnum' not in item_entry:
                    logging.error(f"Item entry is missing required attributes: {item_entry}")
                    return False
                
                room.setdefault('items', []).append(item_entry)
                self.save_rooms()
                logging.info(f"Added item '{item_entry['name']}' to room {room_vnum}.")
                return True
            else:
                logging.error(f"Room {room_vnum} not found.")
                return False

    def remove_item_from_room(self, room_vnum, item_vnum):
        with self.lock:
            room = self.get_room(room_vnum)
            if room:
                items_in_room = room.get('items', [])
                for item in items_in_room:
                    if str(item.get('vnum')) == str(item_vnum):
                        items_in_room.remove(item)
                        self.save_rooms()
                        logging.info(f"Removed item with vnum {item_vnum} from room {room_vnum}.")
                        return True
                logging.error(f"Item with vnum {item_vnum} not found in room {room_vnum}.")
                return False
            else:
                logging.error(f"Room {room_vnum} not found.")
                return False

    def add_player_to_room(self, room_vnum, username, character_name):
        with self.lock:
            room = self.get_room(room_vnum)
            if room:
                if any(p['username'] == username for p in room.get('players', [])):
                    logging.debug(f"Player '{username}' is already in room {room_vnum}. Skipping add.")
                    return False
                player_entry = {
                    'username': username,
                    'character_name': character_name
                }
                room.setdefault('players', []).append(player_entry)
                self.save_rooms()
                logging.info(f"Added player '{character_name}' (username: '{username}') to room {room_vnum}.")
                return True
            else:
                logging.error(f"Room {room_vnum} not found.")
                return False

    def remove_player_from_room(self, room_vnum, username):
        with self.lock:
            room = self.get_room(room_vnum)
            if room and 'players' in room:
                original_count = len(room['players'])
                room['players'] = [p for p in room['players'] if p['username'] != username]
                if len(room['players']) < original_count:
                    self.save_rooms()
                    logging.info(f"Removed player '{username}' from room {room_vnum}.")
                    return True
                else:
                    logging.error(f"Player '{username}' not found in room {room_vnum}.")
                    return False
            else:
                logging.error(f"Room {room_vnum} or players list not found.")
                return False

    def get_players_in_room(self, room_vnum):
        """
        Retrieves the list of players in the specified room.
        """
        room = self.get_room(room_vnum)
        if room:
            return room.get('players', [])
        else:
            logging.error(f"Room with vnum {room_vnum} not found while fetching players.")
            return []

    def clean_duplicate_players(self):
        """
        Cleans duplicate player entries from all rooms.
        """
        with self.lock:
            duplicates_found = False
            for room in self.rooms:
                seen_usernames = set()
                unique_players = []
                duplicates = 0
                for player in room.get('players', []):
                    if player['username'] not in seen_usernames:
                        unique_players.append(player)
                        seen_usernames.add(player['username'])
                    else:
                        duplicates += 1
                if duplicates > 0:
                    room['players'] = unique_players
                    duplicates_found = True
                    logging.info(f"Removed {duplicates} duplicate player(s) from room '{room.get('name', 'Unknown')}'.")
            if duplicates_found:
                self.save_rooms()
                logging.info("Duplicate players cleaned from all rooms.")
            else:
                logging.debug("No duplicate players found in any room.")

    def initialize_rooms(self):
        """
        Initializes rooms by cleaning duplicates and performing any other startup routines.
        """
        self.clean_duplicate_players()
        logging.debug("Rooms initialization complete.")

    def add_mob_to_room(self, room_vnum, mob_entry):
        """Add a mob to a specific room."""
        try:
            with self.lock:
                room = self.get_room(str(room_vnum))
                if room:
                    if 'mobs' not in room:
                        room['mobs'] = []
                    room['mobs'].append(mob_entry)
                    self.save_rooms()
                    return True
                return False
        except Exception as e:
            logging.error(f"Error adding mob to room {room_vnum}: {e}")
            return False

    def get_all_rooms(self):
        """
        Retrieves all rooms managed by the RoomManager.
        """
        with self.lock:
            return self.rooms

    def remove_mob_from_room(self, room_vnum, mob_id):
        """Remove a specific mob instance from a room."""
        with self.lock:
            room = self.get_room(room_vnum)
            if not room:
                logging.error(f"Room {room_vnum} not found when removing mob {mob_id}")
                return False

            mobs = room.get('mobs', [])
            original_count = len(mobs)
            
            # Keep template mobs and remove only the specific instance
            room['mobs'] = [
                mob for mob in mobs 
                if mob.get('is_template', False) or 
                   mob.get('instance_id') != mob_id
            ]
            
            if len(room['mobs']) < original_count:
                self.save_rooms()
                logging.info(f"Removed mob instance {mob_id} from room {room_vnum}")
                return True
            else:
                logging.error(f"Mob instance {mob_id} not found in room {room_vnum}")
                return False

    def add_mob_instance_to_room(self, room_vnum, mob_data):
        """Add a mob instance to a room."""
        with self.lock:
            room = self.get_room(room_vnum)
            if not room:
                logging.error(f"Room {room_vnum} not found when adding mob instance")
                return False

            # Ensure mob_data has required fields
            if not all(k in mob_data for k in ['vnum', 'instance_id']):
                logging.error("Mob data missing required fields")
                return False

            # Add mob instance
            mob_data['is_template'] = False  # Ensure this is marked as an instance
            room['mobs'].append(mob_data)
            self.save_rooms()
            logging.info(f"Added mob instance {mob_data['instance_id']} to room {room_vnum}")
            return True

    def get_mob_template(self, room_vnum, mob_vnum):
        """Get the mob template from a room."""
        with self.lock:
            room = self.get_room(room_vnum)
            if not room:
                return None

            for mob in room.get('mobs', []):
                if (mob.get('is_template', False) and 
                    str(mob.get('vnum')) == str(mob_vnum)):
                    return mob
            return None

    def get_mob_instance_count(self, room_vnum, mob_vnum):
        """Get the count of non-template mob instances in a room."""
        with self.lock:
            room = self.get_room(room_vnum)
            if not room:
                return 0

            return sum(1 for mob in room.get('mobs', [])
                    if not mob.get('is_template', False) and 
                    str(mob.get('vnum')) == str(mob_vnum))

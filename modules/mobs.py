
import logging
from modules.data_handler import load_json, save_json
import threading
import copy
import random
import time
from queue import Queue
from typing import Dict

class MobManager:
    def __init__(self, mobs_file, room_manager):
        self.mobs_file = mobs_file
        self.room_manager = room_manager
        self.lock = threading.RLock()
        self.mobs = load_json(self.mobs_file)
        self.active_mobs = {}  # instance_id -> mob_data
        self.mob_counts = {}  # {room_vnum: {mob_vnum: count}}
        self.spawn_manager = None
        self.respawn_queue = Queue()  # Queue for mob respawns
        self.mob_templates = {}  # Track mob templates per room
        logging.debug(f"MobManager initialized with {len(self.mobs)} mob templates")
        
        # Add these debug lines
        logging.debug(f"MobManager methods: {dir(self)}")
        logging.debug(f"handle_mob_death exists: {'handle_mob_death' in dir(self)}")

        # Load initial mob state
        self.load_initial_state()

    def load_initial_state(self):
        """Load initial mob counts and templates from rooms."""
        try:
            rooms = self.room_manager.get_all_rooms()
            for room in rooms:
                room_vnum = str(room.get('vnum'))
                if not room_vnum:
                    continue

                # Initialize tracking dictionaries
                if room_vnum not in self.mob_counts:
                    self.mob_counts[room_vnum] = {}
                if room_vnum not in self.mob_templates:
                    self.mob_templates[room_vnum] = {}

                # Process mobs in room
                for mob in room.get('mobs', []):
                    mob_vnum = str(mob.get('vnum'))
                    if mob.get('is_template', False):
                        # Store template
                        self.mob_templates[room_vnum][mob_vnum] = mob
                    else:
                        # Count instance
                        if mob_vnum not in self.mob_counts[room_vnum]:
                            self.mob_counts[room_vnum][mob_vnum] = 0
                        self.mob_counts[room_vnum][mob_vnum] += 1

            logging.info("MobManager: Loaded initial mob state")
        except Exception as e:
            logging.error(f"Error loading initial mob state: {e}")

    def get_mob_by_vnum(self, vnum):
        """Get mob template by VNUM."""
        try:
            vnum_str = str(vnum)
            with self.lock:
                mob = next((mob for mob in self.mobs if str(mob["vnum"]) == vnum_str), None)
            if mob:
                logging.debug(f"Found mob: {mob['name']} with vnum: {vnum_str}")
                return copy.deepcopy(mob)
            else:
                logging.error(f"Mob with vnum {vnum_str} not found.")
                return None
        except Exception as e:
            logging.error(f"Error retrieving mob with vnum {vnum}: {e}")
            return None

    def get_mob_by_alias(self, alias):
        """Get mob by alias."""
        alias = alias.lower()
        try:
            with self.lock:
                mob = next((mob for mob in self.mobs if mob.get("alias", "").lower() == alias), None)
            if mob:
                logging.debug(f"Found mob by alias: {mob['name']} with alias: {alias}")
                return copy.deepcopy(mob)
            else:
                logging.error(f"Mob with alias '{alias}' not found.")
                return None
        except Exception as e:
            logging.error(f"Error retrieving mob with alias '{alias}': {e}")
            return None

    def spawn_mob_in_room(self, mob_vnum, room_vnum, room_manager):
        """Spawn a mob instance in the specified room."""
        with self.lock:
            try:
                # Get the mob template
                mob_template = self.get_mob_by_vnum(mob_vnum)
                if not mob_template:
                    logging.error(f"No mob template found for vnum {mob_vnum}")
                    return False

                # Create instance ID and mob instance
                instance_id = f"{mob_vnum}_{int(time.time())}_{random.randint(1000, 9999)}"
                mob_instance = copy.deepcopy(mob_template)
                mob_instance['instance_id'] = instance_id
                mob_instance['room'] = room_vnum
                mob_instance['is_template'] = False

                # Add this block right after creating mob_instance but before adding to room:
                # Store in active_mobs
                self.active_mobs[instance_id] = mob_instance
                logging.debug(f"Added mob {mob_instance['name']} (ID: {instance_id}) to active_mobs")
                logging.debug(f"Active mobs after spawn: {list(self.active_mobs.keys())}")  # Add this debug line

                # Store template if not already stored
                room_key = f"{room_vnum}_{mob_vnum}"
                if room_key not in self.mob_templates:
                    template_copy = copy.deepcopy(mob_template)
                    template_copy['is_template'] = True
                    self.mob_templates[room_key] = template_copy

                # Add to room
                room = room_manager.get_room(room_vnum)
                if not room:
                    logging.error(f"Room {room_vnum} not found")
                    return False

                # Ensure room has mobs list
                if 'mobs' not in room:
                    room['mobs'] = []

                # Add instance to room
                room['mobs'].append({
                    'vnum': mob_vnum,
                    'instance_id': instance_id,
                    'is_template': False
                })

                # Ensure template exists in room
                self.ensure_template_in_room(room, mob_template)
                
                # Save room changes
                room_manager.save_rooms()

                logging.info(f"Successfully spawned mob {mob_vnum} (ID: {instance_id}) in room {room_vnum}")
                return True

            except Exception as e:
                logging.error(f"Error spawning mob: {e}")
                return False

    def ensure_template_in_room(self, room, mob_template):
        """Ensure mob template exists in room configuration."""
        template_exists = False
        for mob in room.get('mobs', []):
            if (mob.get('vnum') == mob_template['vnum'] and 
                mob.get('is_template', False)):
                template_exists = True
                break

        if not template_exists:
            template_entry = {
                'vnum': mob_template['vnum'],
                'is_template': True,
                'quantity': mob_template.get('quantity', 1),
                'max_instances': mob_template.get('max_instances', 1)
            }
            room['mobs'].append(template_entry)
            logging.info(f"Added template for mob {mob_template['vnum']} to room {room.get('vnum')}")

    def remove_mob_from_room(self, instance_id, room_vnum, room_manager):
        """Remove a specific mob instance while preserving template."""
        with self.lock:
            try:
                room = room_manager.get_room(room_vnum)
                if not room:
                    return False

                # Get the mob instance to find its vnum
                mob_instance = self.active_mobs.get(instance_id)  # Changed from get_active_mob
                if not mob_instance:
                    return False

                mob_vnum = mob_instance['vnum']

                # Remove only the specific instance, not the template
                room['mobs'] = [
                    mob for mob in room.get('mobs', [])
                    if (mob.get('instance_id') != instance_id and 
                        (mob.get('is_template', False) or 
                         mob.get('instance_id') != instance_id))
                ]

                # Ensure template remains
                if mob_instance:
                    self.ensure_template_in_room(room, self.get_mob_by_vnum(mob_vnum))

                # Remove from active mobs tracking
                if instance_id in self.active_mobs:
                    del self.active_mobs[instance_id]
                    logging.debug(f"Removed mob instance {instance_id} from active_mobs")

                room_manager.save_rooms()
                logging.info(f"Removed mob instance {instance_id} from room {room_vnum}")
                return True

            except Exception as e:
                logging.error(f"Error removing mob instance: {e}")
                return False

    def handle_mob_death(self, instance_id, room_vnum, room_manager, item_manager):
        """Handle mob death with proper instance cleanup."""
        logging.debug(f"Attempting to handle death of mob {instance_id} in room {room_vnum}")  # Add this
        with self.lock:
            try:
                # Get the mob instance
                mob = self.active_mobs.get(instance_id)
                if not mob:
                    logging.error(f"No mob found for instance ID {instance_id}")
                    return False

                room = room_manager.get_room(room_vnum)
                if not room:
                    logging.error(f"Room {room_vnum} not found")
                    return False

                # Create corpse
                corpse_name = f"corpse of {mob['name']}"
                corpse = {
                    'vnum': 'corpse',
                    'name': corpse_name,
                    'type': 'corpses',
                    'short_desc': f"The corpse of {mob['name']} lies here.",
                    'long_desc': f"This is the corpse of {mob['name']}.",
                    'decay_time': time.time() + 300,
                    'contents': [],
                    'killed_by': None
                }

                # Generate loot
                self.generate_corpse_loot(mob, corpse)

                # Add corpse to room
                room.setdefault('items', []).append(corpse)

                # Remove the mob instance from tracking
                if instance_id in self.active_mobs:
                    del self.active_mobs[instance_id]

                # Update mob count for the room
                mob_vnum = str(mob['vnum'])
                if room_vnum in self.mob_counts and mob_vnum in self.mob_counts[room_vnum]:
                    self.mob_counts[room_vnum][mob_vnum] = max(0, self.mob_counts[room_vnum][mob_vnum] - 1)

                # Remove mob from room's mob list
                room['mobs'] = [m for m in room['mobs'] if m.get('instance_id') != instance_id]

                # Queue for respawn if needed
                template = self.mob_templates.get(f"{room_vnum}_{mob_vnum}")
                if template and template.get('respawn_time'):
                    respawn_data = {
                        'mob_vnum': mob_vnum,
                        'room_vnum': room_vnum,
                        'template': template,
                        'respawn_time': time.time() + template.get('respawn_time', 300)
                    }
                    self.queue_respawn(respawn_data)

                # Save room changes
                room_manager.save_rooms()
                
                logging.info(f"Successfully handled death of mob {mob['name']} (ID: {instance_id}) in room {room_vnum}")
                return True

            except Exception as e:
                logging.error(f"Error handling mob death: {e}")
                return False

    def add_mob(self, mob):
        """Add a new mob template."""
        try:
            with self.lock:
                if any(str(existing_mob["vnum"]) == str(mob["vnum"]) for existing_mob in self.mobs):
                    logging.error(f"Mob with vnum {mob['vnum']} already exists.")
                    return False
                self.mobs.append(mob)
                logging.info(f"Added mob: {mob['name']}")
                self.save_mobs()
                return True
        except Exception as e:
            logging.error(f"Error adding mob '{mob['name']}': {e}")
            return False

    def remove_mob(self, vnum):
        """Remove a mob template."""
        try:
            vnum_str = str(vnum)
            with self.lock:
                mob = next((mob for mob in self.mobs if str(mob["vnum"]) == vnum_str), None)
                if mob:
                    self.mobs.remove(mob)
                    logging.info(f"Removed mob: {mob['name']} with vnum: {vnum_str}")
                    self.save_mobs()
                    return True
                logging.error(f"Mob with vnum {vnum_str} does not exist.")
                return False
        except Exception as e:
            logging.error(f"Error removing mob with vnum {vnum}: {e}")
            return False

    def save_mobs(self):
        """Save mob templates to file."""
        try:
            with self.lock:
                save_json(self.mobs_file, self.mobs)
            logging.info("Mobs data saved.")
        except Exception as e:
            logging.error(f"Error saving mobs: {e}")

    def get_active_mob(self, instance_id):
        """Get a full mob instance by its ID."""
        return self.active_mobs.get(instance_id)

    def update_mob_stats(self, instance_id, new_stats):
        """Update a mob instance's current stats."""
        with self.lock:
            if instance_id in self.active_mobs:
                self.active_mobs[instance_id]['stats'].update(new_stats)
                return True
            return False

    def move_mob(self, instance_id, from_room, to_room, room_manager):
        """Move a mob from one room to another."""
        with self.lock:
            if instance_id not in self.active_mobs:
                return False

            mob = self.active_mobs[instance_id]

            # Remove from current room
            if not self.remove_mob_from_room(instance_id, from_room, room_manager):
                return False

            # Add to new room
            mob['room'] = to_room
            result = self.spawn_mob_in_room(mob['vnum'], to_room, room_manager)

            if not result:
                # Try to put back in original room if move failed
                self.spawn_mob_in_room(mob['vnum'], from_room, room_manager)
                return False

            return True

    def calculate_mob_attack(self, mob):
        """Calculate mob's attack damage."""
        ferocity = mob['stats'].get('Ferocity', 3)
        attack_power = random.randint(ferocity, ferocity * 2)
        return attack_power

    def calculate_mob_defense(self, mob):
        """Calculate mob's defense value."""
        resilience = mob['stats'].get('Resilience', 3)
        return resilience

    def calculate_mob_evasion(self, mob):
        """Calculate mob's evasion chance."""
        evasiveness = mob['stats'].get('Evasiveness', 3)
        return evasiveness

    def should_mob_flee(self, mob):
        """Determine if a mob should attempt to flee."""
        if mob.get('is_aggressive', False):
            return False

        current_hp = mob['current_hp']
        max_hp = mob['stats']['HP']
        flee_threshold = mob.get('flee_threshold', 20)  # Flee at 20% HP by default

        return (current_hp / max_hp * 100) <= flee_threshold

    def generate_mob_identifier(self, mob_name, room):
        """Generate a unique identifier for multiple instances of the same mob."""
        existing_mobs = [mob for mob in room.get('mobs', []) 
                        if mob_name in self.get_active_mob(mob.get('instance_id', '')).get('name', '')]
        mob_count = len(existing_mobs) + 1
        return f"{mob_name} ({mob_count})"

    def respawn_mob_check(self, room_vnum, mob_vnum, room_manager):
        """Check if a mob should be respawned."""
        room = room_manager.get_room(room_vnum)
        if not room:
            return False

        mob_template = self.get_mob_by_vnum(mob_vnum)
        if not mob_template:
            return False

        # Count current instances of this mob type
        current_count = sum(1 for mob in room.get('mobs', []) 
                          if mob.get('vnum') == mob_vnum)

        max_instances = mob_template.get('max_instances', 1)

        if current_count < max_instances:
            self.spawn_mob_in_room(mob_vnum, room_vnum, room_manager)
            return True

        return False

    def create_instance(self, vnum, room_vnum):
        """Create a new mob instance with proper tracking."""
        with self.lock:
            template = self.get_mob_by_vnum(vnum)
            if not template:
                return None

            instance_id = f"{vnum}_{int(time.time())}_{random.randint(1000, 9999)}"
            
            # Create minimal instance data for room storage
            room_instance = {
                'vnum': vnum,
                'instance_id': instance_id,
                'is_template': False
            }
            
            # Create full instance data for memory
            full_instance = copy.deepcopy(template)
            full_instance.update({
                'instance_id': instance_id,
                'room': room_vnum,  # Use 'room' for consistency
                'is_template': False
            })
            
            # Update tracking
            self.active_mobs[instance_id] = full_instance
            self.mob_counts.setdefault(room_vnum, {})
            self.mob_counts[room_vnum][str(vnum)] = self.mob_counts[room_vnum].get(str(vnum), 0) + 1
            
            return room_instance

    def remove_instance(self, instance_id):
        """Remove a mob instance from tracking."""
        with self.lock:
            if instance_id in self.active_mobs:
                mob = self.active_mobs[instance_id]
                room_vnum = mob['room']  # Note: using 'room' instead of 'room_vnum'
                mob_vnum = str(mob['vnum'])
                
                # Update counts
                if room_vnum in self.mob_counts and mob_vnum in self.mob_counts[room_vnum]:
                    self.mob_counts[room_vnum][mob_vnum] = max(0, self.mob_counts[room_vnum][mob_vnum] - 1)
                
                # Remove from active mobs
                del self.active_mobs[instance_id]
                return True
            return False

    def queue_respawn(self, mob_data: Dict):
        """Queue a mob for respawn."""
        try:
            # Get room and mob info
            room_vnum = str(mob_data.get('room_vnum'))
            mob_vnum = str(mob_data.get('vnum'))
            
            # Get the template from the room
            room = self.room_manager.get_room(room_vnum)
            if not room:
                logging.error(f"Room {room_vnum} not found for respawn")
                return False
                
            # Find template
            template = next(
                (mob for mob in room.get('mobs', [])
                 if mob.get('is_template', False) and str(mob.get('vnum')) == mob_vnum),
                None
            )
            
            if not template:
                logging.error(f"No template found for mob {mob_vnum} in room {room_vnum}")
                return False
                
            # Calculate respawn time
            respawn_time = time.time() + template.get('respawn_time', 300)  # Default 5 minutes
            
            # Add to respawn queue
            respawn_data = {
                'mob_vnum': mob_vnum,
                'room_vnum': room_vnum,
                'template': template,
                'respawn_time': respawn_time
            }
            
            self.respawn_queue.put(respawn_data)
            logging.info(f"Queued mob {mob_vnum} for respawn at {time.ctime(respawn_time)}")
            return True
                
        except Exception as e:
            logging.error(f"Error queuing mob respawn: {e}")
            return False

    def _handle_respawn(self, respawn_data: Dict):
        """Process a queued respawn with proper instance tracking."""
        try:
            # Check if it's time to respawn
            if time.time() < respawn_data['respawn_time']:
                # Put it back in the queue if not ready
                self.respawn_queue.put(respawn_data)
                return

            room_vnum = str(respawn_data['room_vnum'])
            mob_vnum = str(respawn_data['mob_vnum'])
            template = respawn_data['template']

            with self.lock:
                # Check instance limits
                current_count = self._count_mob_instances(room_vnum, mob_vnum)
                max_instances = int(template.get('max_instances', 1))

                if current_count >= max_instances:
                    logging.info(f"Skipped respawn of mob {mob_vnum} in room {room_vnum}: at max instances ({current_count}/{max_instances})")
                    return

                # Create new instance
                if self._spawn_mob_instance(room_vnum, template):
                    logging.info(f"Respawned mob {mob_vnum} in room {room_vnum}")
                    # Update instance count
                    if room_vnum not in self.mob_counts:
                        self.mob_counts[room_vnum] = {}
                    if mob_vnum not in self.mob_counts[room_vnum]:
                        self.mob_counts[room_vnum][mob_vnum] = 0
                    self.mob_counts[room_vnum][mob_vnum] += 1

        except Exception as e:
            logging.error(f"Error handling respawn: {e}")

    def _count_mob_instances(self, room_vnum, mob_vnum):
        """Count the number of instances of a mob in a room."""
        return sum(1 for mob in self.active_mobs.get(room_vnum, []) if mob.get('vnum') == mob_vnum)

    def _spawn_mob_instance(self, room_vnum, template):
        """Spawn a new mob instance based on the template."""
        try:
            mob_instance = copy.deepcopy(template)
            mob_instance['is_template'] = False
            mob_instance['instance_id'] = f"{template['vnum']}_{int(time.time())}_{random.randint(1000, 9999)}"
            mob_instance['room'] = room_vnum

            self.active_mobs[mob_instance['instance_id']] = mob_instance

            room = self.room_manager.get_room(room_vnum)
            if not room:
                logging.error(f"Room {room_vnum} not found for spawning mob instance")
                return False

            room.setdefault('mobs', []).append({
                'vnum': mob_instance['vnum'],
                'instance_id': mob_instance['instance_id'],
                'is_template': False
            })

            self.room_manager.save_rooms()
            return True

        except Exception as e:
            logging.error(f"Error spawning mob instance: {e}")
            return False

    def generate_corpse_loot(self, mob, corpse):
        """Generate loot for a mob corpse."""
        try:
            # Process loot pool
            loot_pool = mob.get('loot_pool', [])
            for loot in loot_pool:
                if random.uniform(0, 100) <= loot.get('drop_rate', 0):
                    corpse['contents'].append({
                        'vnum': loot['vnum'],
                        'type': loot['type'],
                        'quantity': loot.get('quantity', 1)
                    })

            # Handle gold drops
            gold_base = mob.get('gold', 0)
            if gold_base > 0:
                gold_amount = random.randint(gold_base, int(gold_base * 1.5))
                corpse['contents'].append({
                    'vnum': 'gold',
                    'type': 'currency',
                    'quantity': gold_amount
                })

            logging.debug(f"Generated loot for mob {mob['name']}")
            
        except Exception as e:
            logging.error(f"Error generating corpse loot: {e}")

class MobSpawnManager:
    def __init__(self, mob_manager, room_manager):
        self.mob_manager = mob_manager
        self.room_manager = room_manager
        self.running = True
        self.respawn_queue = Queue()
        self.lock = threading.RLock()
        self.spawn_thread = None

    def start(self):
        """Start the spawn manager thread."""
        self.spawn_thread = threading.Thread(target=self._spawn_loop, daemon=True)
        self.spawn_thread.start()
        logging.info("Started mob spawn manager")
        
    def _spawn_loop(self):
        """Main loop for processing spawns and respawns."""
        while self.running:
            try:
                # Process respawn queue
                while not self.respawn_queue.empty():
                    respawn_data = self.respawn_queue.get_nowait()
                    self._handle_respawn(respawn_data)
                
                # Check and maintain spawn counts
                self._maintain_spawn_counts()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logging.error(f"Error in spawn loop: {e}")
                time.sleep(10)  # Keep trying even if there's an error

    def _maintain_spawn_counts(self):
        """Ensure rooms maintain their desired mob quantities."""
        with self.lock:
            try:
                rooms = self.room_manager.get_all_rooms()
                for room in rooms:
                    room_vnum = str(room.get('vnum'))
                    
                    # Check each mob template in the room
                    for mob in room.get('mobs', []):
                        if mob.get('is_template', False):  # Only process templates
                            mob_vnum = str(mob.get('vnum'))
                            desired_count = int(mob.get('quantity', 1))
                            current_count = self.mob_manager.mob_counts.get(room_vnum, {}).get(mob_vnum, 0)
                            
                            # Spawn more if needed
                            needed = max(0, desired_count - current_count)
                            for _ in range(needed):
                                self._spawn_mob_instance(room_vnum, mob)
                                
            except Exception as e:
                logging.error(f"Error maintaining spawn counts: {e}")

    def _spawn_mob_instance(self, room_vnum, template):
        """Spawn a new mob instance in a room."""
        try:
            mob_vnum = str(template['vnum'])
            current_count = self.mob_manager.mob_counts.get(room_vnum, {}).get(mob_vnum, 0)
            max_instances = template.get('max_instances', 1)

            if current_count >= max_instances:
                return False

            # Create instance through mob manager
            room_instance = self.mob_manager.create_instance(mob_vnum, room_vnum)
            if not room_instance:
                return False

            # Add to room
            if self.room_manager.add_mob_to_room(room_vnum, room_instance):
                logging.info(f"Spawned mob {mob_vnum} in room {room_vnum}")
                return True
            
            # Cleanup if room add fails
            self.mob_manager.remove_instance(room_instance['instance_id'])
            return False

        except Exception as e:
            logging.error(f"Error spawning mob instance: {e}")
            return False

    def queue_respawn(self, respawn_data):
        """Queue a mob for respawn."""
        try:
            self.respawn_queue.put(respawn_data)
            logging.info(
                f"Queued mob {respawn_data['mob_vnum']} for respawn in room "
                f"{respawn_data['room_vnum']} at {time.ctime(respawn_data['respawn_time'])}"
            )
            return True
        except Exception as e:
            logging.error(f"Error queuing mob respawn: {e}")
            return False

    def _handle_respawn(self, respawn_data):
        """Process a queued respawn."""
        try:
            # Check if it's time to respawn
            if time.time() < respawn_data['respawn_time']:
                # Put it back in the queue if not ready
                self.respawn_queue.put(respawn_data)
                return

            room_vnum = str(respawn_data['room_vnum'])
            template = respawn_data['template']
            
            with self.lock:
                # Attempt to spawn the mob
                if self._spawn_mob_instance(room_vnum, template):
                    logging.info(f"Respawned mob {template['vnum']} in room {room_vnum}")

        except Exception as e:
            logging.error(f"Error handling respawn: {e}")

    def stop(self):
        """Stop the spawn manager cleanly."""
        self.running = False
        if self.spawn_thread:
            self.spawn_thread.join(timeout=1.0)
        logging.info("Stopped mob spawn manager")


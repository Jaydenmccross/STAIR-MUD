
# modules/commands.py
from typing import Dict, Any, Optional, List
import socket
import logging
import copy
import random
import time
import re
import threading

from modules.character import (
    calculate_total_stats, 
    ensure_character_compatibility, 
    display_character_sheet,
    ACCOUNT_LEVELS,
    WANDERER_SKILLS
)
from modules.skills import SkillManager
from modules.spells import SpellManager
from modules.items import ItemManager
from modules.rooms import RoomManager
from modules.mobs import MobManager
from modules.account_manager import AccountManager
from .combat import CombatManager

# Define DIRECTION_ALIASES globally
DIRECTION_ALIASES = {
    'n': 'north',
    's': 'south',
    'e': 'east',
    'w': 'west',
    'ne': 'northeast',
    'nw': 'northwest',
    'se': 'southeast',
    'sw': 'southwest',
    'up': 'up',
    'down': 'down',
}

# Initialize logging configuration
logging.basicConfig(
    filename='logs/server.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def cleanup_player(username, character, room_manager, account_manager, client_socket):
    """
    Cleans up the player's presence from the game, ensuring they are removed from rooms
    and the list of connected clients.
    """
    try:
        # Remove player from their current room
        room_vnum = character.get('room')
        room = room_manager.get_room(room_vnum)
        if room:
            room_manager.remove_player_from_room(room_vnum, username)
            logging.debug(f"Removed player '{username}' from room {room_vnum}.")
        else:
            logging.warning(f"Room with vnum {room_vnum} not found for player '{username}'.")
    except Exception as e:
        logging.error(f"Error during cleanup for player '{username}': {e}")
    finally:
        try:
            # Remove player from connected clients
            account_manager.remove_connected_client(username)
            logging.info(f"Cleaned up player '{username}' from connected clients.")
        except Exception as e:
            logging.error(f"Error removing connected client for player '{username}': {e}")
        finally:
            try:
                client_socket.close()
                logging.debug(f"Closed client socket for '{username}'.")
            except Exception as e:
                logging.error(f"Error closing socket for '{username}': {e}")

def handle_command(command, character, username, client_socket, room_manager, 
                  item_manager, mob_manager, account_manager, skill_manager, 
                  spell_manager, combat_manager, user_role):
    """
    Main command handler with admin permission checks
    """
    if not command:
        try:
            handle_look(character, client_socket, room_manager, item_manager, mob_manager, account_manager)
            return
        except Exception as e:
            logging.error(f"Error executing handle_look for '{character['name']}': {e}")
            client_socket.sendall(b"An error occurred while processing your command.\n")
            cleanup_player(username, character, room_manager, account_manager, client_socket)
            return

    parts = command.split()
    cmd = parts[0].lower().lstrip('/')  # Strip leading '/' from chat commands
    args = parts[1:]

    cmd_original = cmd  # Store the original command before mapping

    # Chat command handling
    chat_commands = ['say', 'whisper', 'ooc', 'shout', 'tell', 'reply', 'r', 'broadcast']
    if cmd in chat_commands:
        try:
            # Check for admin privileges if using broadcast
            if cmd == 'broadcast' and character.get('account_level', 1) < ACCOUNT_LEVELS['admin']:
                client_socket.sendall(b"You don't have permission to use the broadcast command.\n")
                return
            
            handle_chat_command(cmd, args, character, client_socket, room_manager, username, character.get('last_tell'), user_role, account_manager)
            return
        except Exception as e:
            logging.error(f"Error executing chat command '{cmd}' for '{character['name']}': {e}")
            client_socket.sendall(b"An error occurred while processing your chat command.\n")
            cleanup_player(username, character, room_manager, account_manager, client_socket)
            return

    # Admin command mappings (require admin privileges)
    admin_commands = {
        '@summon': 'summon',
        '@isummon': 'summon',
        '@asummon': 'summon',
        '@wsummon': 'summon',
        '@csummon': 'summon',
        '@msummon': 'summon',
        '@wsum': 'summon',
        '@asum': 'summon',
        '@csum': 'summon',
        '@msum': 'summon',
        '@isum': 'summon',
        '@bagsum': 'summon',
        'destroy': 'destroy'
    }

    # Regular command mappings
    regular_commands = {
        'c': 'character',
        'char': 'character',
        'character': 'character',
        'cast': 'cast',
        'skill': 'skill_use',
        'help': 'help',
        'eat': 'eat',
        'drink': 'drink',
        'read': 'read',
        'put': 'put',
        'place': 'put',
        'lock': 'lock',
        'unlock': 'unlock'
    }

    # Check if command is an admin command
    if cmd in admin_commands:
        if character.get('account_level', 1) < ACCOUNT_LEVELS['admin']:
            client_socket.sendall(b"You don't have permission to use this command.\n")
            return
        cmd = admin_commands[cmd]
    elif cmd in regular_commands:
        cmd = regular_commands[cmd]

    try:
        if cmd in DIRECTION_ALIASES or cmd in DIRECTION_ALIASES.values():
            handle_movement(cmd_original, character, client_socket, room_manager, item_manager, mob_manager, account_manager, username)
        
        elif cmd in ['look', 'l']:
            handle_look(character, client_socket, room_manager, item_manager, mob_manager, account_manager)
        
        elif cmd == 'get':
            handle_get(username, character, args, client_socket, room_manager, item_manager, account_manager)
        
        elif cmd == 'drop':
            handle_drop(username, character, args, client_socket, room_manager, item_manager, account_manager)
        
        elif cmd == 'examine':
            handle_examine(character, args, client_socket, room_manager, item_manager, mob_manager)
        
        elif cmd in ['wear', 'wield', 'equip', 'brandish']:
            handle_equip(username, character, args, client_socket, room_manager, item_manager, account_manager)
        
        elif cmd in ['unequip', 'remove']:
            handle_unequip(username, character, args, client_socket, room_manager, item_manager, account_manager)
        
        elif cmd in ['inventory', 'inv', 'i']:
            handle_inventory(character, client_socket)
        
        elif cmd in ['attack', 'kill']:
            target_name = ' '.join(args) if args else None
            combat_manager.initiate_combat(
                character=character,
                target_name=target_name,
                client_socket=client_socket,
                room_manager=room_manager,
                mob_manager=mob_manager,
                account_manager=account_manager,
                item_manager=item_manager
            )
        
        elif cmd == 'skills':
            handle_skills(character, client_socket, skill_manager)
        
        elif cmd == 'skill_use':
            handle_skill_use(username, character, args, client_socket, skill_manager, account_manager, room_manager, mob_manager, item_manager)
        
        elif cmd == 'cast':
            handle_cast(username, character, args, client_socket, spell_manager, account_manager)
        
        elif cmd == 'use':
            handle_use(command, username, character, client_socket, room_manager, item_manager, mob_manager, account_manager, skill_manager)
        
        elif cmd == 'eat':
            handle_eat(username, character, args, client_socket, account_manager)
        
        elif cmd == 'drink':
            handle_drink(username, character, args, client_socket, account_manager)
        
        elif cmd == 'help':
            handle_help(args, client_socket, character, room_manager, item_manager, mob_manager, account_manager)
        
        elif cmd == 'flee':
            if character.get('in_combat', False):
                combat_manager.handle_flee(
                    character=character, 
                    client_socket=client_socket,
                    room_manager=room_manager,
                    mob_manager=mob_manager,
                    account_manager=account_manager
                )
            else:
                client_socket.sendall(b"You're not in combat!\n")
        
        elif cmd == 'character':
            display_character_sheet(client_socket, character)
        
        elif cmd == 'put':
            handle_put(username, character, args, client_socket, room_manager, item_manager, account_manager)
            
        elif cmd == 'lock':
            handle_lock(username, character, args, client_socket, room_manager, item_manager, account_manager)
            
        elif cmd == 'unlock':
            handle_unlock(username, character, args, client_socket, room_manager, item_manager, account_manager)
        
        elif cmd == 'summon':
            if character.get('account_level', 1) >= ACCOUNT_LEVELS['admin']:
                handle_summon_command(cmd_original, username, character, args, client_socket, room_manager, item_manager, mob_manager, account_manager)
            else:
                client_socket.sendall(b"You don't have permission to use the summon command.\n")
        
        elif cmd == 'destroy':
            if character.get('account_level', 1) >= ACCOUNT_LEVELS['admin']:
                handle_destroy_command(username, character, args, client_socket, room_manager, item_manager, mob_manager, account_manager)
            else:
                client_socket.sendall(b"You don't have permission to use the destroy command.\n")
        
        elif cmd == 'read':
            handle_read(character, args, client_socket, room_manager, item_manager)
        
        else:
            client_socket.sendall(b"Unknown command.\n")

    except Exception as e:
        logging.error(f"Error handling command '{cmd_original}' for character '{character['name']}': {e}")
        client_socket.sendall(b"An unexpected error occurred while processing your command.\n")
        cleanup_player(username, character, room_manager, account_manager, client_socket)

def handle_look(character, client_socket, room_manager, item_manager, mob_manager, account_manager):
    """Handle the look command."""
    try:
        room_vnum = character.get('room')
        room = room_manager.get_room(room_vnum)

        if not room:
            client_socket.sendall(b"You are in an unknown place.\n")
            return

        room_title = room.get('name', 'An Unnamed Room')
        # Use description field with long_desc as fallback
        room_description = room.get('description') or room.get('long_desc', 'You see nothing special.')
        exits = room.get('exits', {})
        items = room.get('items', [])
        mobs = room.get('mobs', [])
        players = room_manager.get_players_in_room(room_vnum)

        response = []
        response.append(f"{room_title}")
        response.append(f"{room_description}")

        # Show exits
        if exits:
            exit_list = ', '.join([key.lower() for key in exits.keys()])
            response.append(f"Exits: {exit_list}")
        else:
            response.append("No obvious exits.")

        # Show mobs (using short_desc)
        if mobs:
            response.append("\nCreatures present:")
            mob_groups = {}
            for mob_entry in mobs:
                # Skip template entries
                if mob_entry.get('is_template', False):
                    continue
                mob = mob_manager.get_mob_by_vnum(mob_entry['vnum'])
                if mob:
                    short_desc = mob.get('short_desc', mob.get('name', 'A creature'))
                    mob_groups[short_desc] = mob_groups.get(short_desc, 0) + 1

            for desc, count in mob_groups.items():
                if count > 1:
                    response.append(f"- {desc} (x{count})")
                else:
                    response.append(f"- {desc}")

        # Show items in the room
        if items:
            response.append("\nYou see:")
            item_groups = {}  # Group similar items together
            
            for item_entry in items:
                # Handle currency (gold) specially
                if item_entry.get('vnum') == 'gold':
                    quantity = item_entry.get('quantity', 0)
                    response.append(f"- {quantity} gold coins lie here")
                    continue
                    
                # Handle corpses specially
                if item_entry.get('type') == 'corpses':
                    response.append(f"- {item_entry.get('short_desc', 'A corpse lies here')}")
                    continue

                # Handle containers specially
                if item_entry.get('type') == 'containers':
                    container_desc = item_entry.get('short_desc', f"- {item_entry.get('name', 'A container')} sits here")
                    if item_entry.get('flags', {}).get('Locked', False):
                        container_desc += " (locked)"
                    response.append(container_desc)
                    continue

                # For regular items, look up the base item data
                base_item = item_manager.get_item_by_vnum(item_entry.get('vnum'), item_entry.get('type'))
                if base_item:
                    item_desc = base_item.get('short_desc', base_item.get('name', 'An item'))
                    key = (item_desc, base_item.get('type'))
                    
                    # Initialize or increment counter for this item type
                    if key not in item_groups:
                        item_groups[key] = {
                            'desc': item_desc,
                            'count': 0,
                            'type': base_item.get('type')
                        }
                    item_groups[key]['count'] += item_entry.get('quantity', 1)

            # Add grouped items to response
            for item_data in item_groups.values():
                if item_data['count'] > 1:
                    response.append(f"- {item_data['desc']} (x{item_data['count']})")
                else:
                    response.append(f"- {item_data['desc']}")

        # Show other players
        other_players = [p for p in players if p['username'] != character.get('username')]
        if other_players:
            response.append("\nOther players here:")
            for player in other_players:
                response.append(f"- {player.get('name', 'Someone')}")

        client_socket.sendall('\n'.join(response).encode() + b'\n')

    except Exception as e:
        logging.error(f"Error in handle_look: {e}")
        client_socket.sendall(b"An error occurred while looking around.\n")

def handle_summon_command(cmd_original, username, character, args, client_socket, room_manager, item_manager, mob_manager, account_manager):
    """Handle summon commands (admin only)"""
    if character.get('account_level', 1) < ACCOUNT_LEVELS['admin']:
        client_socket.sendall(b"You don't have permission to use summon commands.\n")
        return

    if not args or len(args) < 1:
        client_socket.sendall(b"Usage: @<isum|asum|wsum|csum|msum|bagsum> <vnum> [inv|here]\n")
        return

    if not cmd_original.startswith('@'):
        client_socket.sendall(b"Invalid summon command.\n")
        return

    vnum = args[0]
    location = args[1].lower() if len(args) > 1 else 'inv'

    # Mapping of summon commands to item types
    item_type_map = {
        '@isum': 'items',
        '@asum': 'armors',
        '@wsum': 'weapons',
        '@csum': 'consumables',
        '@msum': 'mob',
        '@bagsum': 'containers'
    }

    cmd_lower = cmd_original.lower()
    item_type = item_type_map.get(cmd_lower)

    if not item_type:
        client_socket.sendall(b"Invalid summon command.\n")
        return

    if item_type == 'mob':
        mob = mob_manager.get_mob_by_vnum(vnum)
        if mob:
            current_room = room_manager.get_room(character['room'])
            if current_room:
                current_room.setdefault('mobs', []).append(copy.deepcopy(mob))
                room_manager.save_rooms()
                client_socket.sendall(f"Mob '{mob.get('name', 'Unknown')}' summoned in the room.\n".encode())
            else:
                client_socket.sendall(b"Current room not found.\n")
        else:
            client_socket.sendall(b"Mob not found.\n")
    else:
        item = item_manager.get_item_by_vnum(vnum, item_type)
        if item:
            if location == 'inv':
                try:
                    item_copy = copy.deepcopy(item)
                    character.setdefault('inventory', []).append(item_copy)
                    
                    # If this is a container that requires a key, also create and give the key
                    if (item_type == 'containers' and 
                        item_copy.get('flags', {}).get('Key_Required') and 
                        item_copy.get('key_name')):
                        
                        # Create key using the container's defined key name
                        key_item = {
                            'vnum': f"key_{vnum}",
                            'name': f"a {item_copy['key_name']}",
                            'type': 'keys',
                            'key_name': item_copy['key_name'],
                            'short_desc': f"A {item_copy['key_name']} for {item_copy['name']}",
                            'long_desc': f"This is a {item_copy['key_name']} made specifically for {item_copy['name']}.",
                            'visible': True  # Add visibility flag
                        }
                        character['inventory'].append(key_item)
                        logging.info(f"Created key '{key_item['name']}' for container '{item_copy['name']}'")
                        
                    account_manager.update_character(username, character)
                    client_socket.sendall(f"Item '{item.get('name', 'Unknown')}' summoned to your inventory.\n".encode())
                    
                    # Notify about the key if one was created
                    if 'key_item' in locals():
                        client_socket.sendall(b"A key for the container was also added to your inventory.\n")
                        
                except Exception as e:
                    logging.error(f"Error during item summon to inventory: {e}")
                    client_socket.sendall(b"An error occurred while summoning the item to your inventory.\n")
            elif location == 'here':
                current_room = room_manager.get_room(character['room'])
                if current_room:
                    item_copy = copy.deepcopy(item)
                    # If container is marked as immobile, set the flag
                    if item_type == 'containers' and item_copy.get('flags', {}).get('Immobile', False):
                        item_copy['immobile'] = True
                        
                    current_room.setdefault('items', []).append(item_copy)
                    
                    # If this is a container that requires a key, also create and place the key
                    if (item_type == 'containers' and 
                        item_copy.get('flags', {}).get('Key_Required') and 
                        item_copy.get('key_name')):
                        
                        # Create key using the container's defined key name
                        key_item = {
                            'vnum': f"key_{vnum}",
                            'name': f"a {item_copy['key_name']}",
                            'type': 'keys',
                            'key_name': item_copy['key_name'],
                            'short_desc': f"A {item_copy['key_name']} for {item_copy['name']}",
                            'long_desc': f"This is a {item_copy['key_name']} made specifically for {item_copy['name']}.",
                            'visible': True  # Add visibility flag
                        }
                        current_room['items'].append(key_item)
                        logging.info(f"Created key '{key_item['name']}' for container '{item_copy['name']}' in room")
                        
                    room_manager.save_rooms()
                    client_socket.sendall(f"Item '{item.get('name', 'Unknown')}' summoned in the room.\n".encode())
                    
                    # Notify about the key if one was created
                    if 'key_item' in locals():
                        client_socket.sendall(b"A key for the container was also placed in the room.\n")
                else:
                    client_socket.sendall(b"Current room not found.\n")
            else:
                client_socket.sendall(b"Invalid location. Use 'inv' or 'here'.\n")
        else:
            client_socket.sendall(b"Item not found.\n")

def handle_destroy_command(username, character, args, client_socket, room_manager, item_manager, mob_manager, account_manager):
    if not args:
        client_socket.sendall(b"Usage: destroy <item_name|mob_name> [here|inv]\n")
        return

    # Default location is 'inv'
    if args[-1].lower() in ['here', 'inv']:
        location = args[-1].lower()
        target_name = ' '.join(args[:-1]).lower()
    else:
        location = 'inv'
        target_name = ' '.join(args).lower()

    if location == 'inv':
        inventory = character.get('inventory', [])
        # Find the item in the inventory
        item = find_item_in_inventory(target_name, inventory)

        if not item:
            client_socket.sendall(f"You don't have '{target_name}' in your inventory.\n".encode())
            return

        quantity = item.get('quantity', 1)
        if quantity > 1:
            item['quantity'] = quantity - 1
        else:
            inventory.remove(item)

        account_manager.update_character(username, character)
        client_socket.sendall(f"You destroyed '{item.get('name', 'Unknown')}' from your inventory.\n".encode())
        logging.info(f"Character '{character['name']}' destroyed '{item.get('name', 'Unknown')}' from their inventory.")
    elif location == 'here':
        room_vnum = character['room']
        current_room = room_manager.get_room(room_vnum)
        if not current_room:
            client_socket.sendall(b"Error: Current room not found.\n")
            return

        # Check for items in the room
        room_items = current_room.get('items', [])
        found_item_entry, room_item = find_item_in_room(target_name, room_items, item_manager)

        if found_item_entry:
            # Check if the item is immobile
            if found_item_entry.get('immobile', False) or (room_item and room_item.get('immobile', False)):
                client_socket.sendall(b"That cannot be destroyed.\n")
                return

            quantity = found_item_entry.get('quantity', 1)
            if quantity > 1:
                found_item_entry['quantity'] = quantity - 1
            else:
                room_items.remove(found_item_entry)
            room_manager.save_rooms()
            client_socket.sendall(f"You destroyed '{room_item.get('name', 'Unknown')}' from the room.\n".encode())
            logging.info(f"Character '{character['name']}' destroyed '{room_item.get('name', 'Unknown')}' from room {room_vnum}.")
            return

        # Check for mobs in the room
        room_mobs = current_room.get('mobs', [])
        mob_entry = find_mob_in_room(target_name, room_mobs, mob_manager)

        if mob_entry:
            room_mobs.remove(mob_entry)
            room_manager.save_rooms()
            mob = mob_manager.get_mob_by_vnum(mob_entry['vnum'])
            mob_name = mob.get('name', 'Unknown') if mob else 'Unknown'
            client_socket.sendall(f"You destroyed '{mob_name}' from the room.\n".encode())
            logging.info(f"Character '{character['name']}' destroyed mob '{mob_name}' from room {room_vnum}.")
        else:
            client_socket.sendall(f"There is no '{target_name}' here to destroy.\n".encode())
    else:
        client_socket.sendall(b"Invalid location. Use 'here' or 'inv'.\n")

def handle_chat_command(cmd, args, character, client_socket, room_manager, username, last_tell_sender, user_role, account_manager):
    """
    Handle chat commands with admin checks for broadcast
    """
    # ANSI color codes
    COLOR_GREEN = "\033[32m"
    COLOR_DARK_BLUE = "\033[34m"
    COLOR_RED = "\033[31m"
    COLOR_LIGHT_BLUE = "\033[36m"
    COLOR_WHITE = "\033[37m"
    COLOR_RESET = "\033[0m"

    room_vnum = character.get('room')
    room = room_manager.get_room(room_vnum)

    if not room:
        client_socket.sendall(b"You are in an unknown place.\n")
        return

    if cmd == 'say':
        message = ' '.join(args)
        client_socket.sendall(f'{COLOR_GREEN}You say: "{message}"{COLOR_RESET}\n'.encode())
        
        players = room_manager.get_players_in_room(room_vnum)
        for player in players:
            if player['username'] != username:
                account_manager.send_message_to_client(player['username'], 
                    f"{COLOR_GREEN}{character['name']} says: \"{message}\"{COLOR_RESET}\n")

    elif cmd == 'shout':
        message = ' '.join(args)
        client_socket.sendall(f'{COLOR_RED}You shout: "{message}"{COLOR_RESET}\n'.encode())
        
        shout_message = f"{COLOR_RED}{character['name']} shouts: \"{message}\"{COLOR_RESET}\n"
        for player in account_manager.connected_clients.keys():
            if player != username:
                account_manager.send_message_to_client(player, shout_message)

    elif cmd == 'whisper':
        if len(args) < 2:
            client_socket.sendall(b"Usage: /whisper <name> <message>\n")
            return
            
        target_character_name = args[0]
        message = ' '.join(args[1:])
        target_username = account_manager.get_username_by_character_name(target_character_name)

        if target_username and account_manager.is_connected(target_username):
            account_manager.send_message_to_client(target_username, 
                f"{COLOR_DARK_BLUE}{character['name']} whispers to you: \"{message}\"{COLOR_RESET}\n")
            client_socket.sendall(
                f'{COLOR_DARK_BLUE}You whisper to {target_character_name}: "{message}"{COLOR_RESET}\n'.encode())
        else:
            client_socket.sendall(f"{target_character_name} is not online.\n".encode())

    elif cmd == 'ooc':
        message = ' '.join(args)
        ooc_message = f"{COLOR_LIGHT_BLUE}(OOC) {character['name']}: \"{message}\"{COLOR_RESET}\n"
        account_manager.broadcast_to_all_clients(ooc_message)

    elif cmd == 'tell':
        if len(args) < 2:
            client_socket.sendall(b"Usage: /tell <player name> <message>\n")
            return
            
        target_character_name = args[0]
        message = ' '.join(args[1:])
        target_username = account_manager.get_username_by_character_name(target_character_name)

        if target_username and account_manager.is_connected(target_username):
            account_manager.send_message_to_client(target_username, 
                f"{COLOR_DARK_BLUE}{character['name']} tells you: \"{message}\"{COLOR_RESET}\n")
            client_socket.sendall(
                f'{COLOR_DARK_BLUE}You tell {target_character_name}: "{message}"{COLOR_RESET}\n'.encode())
            account_manager.set_last_tell_sender(target_username, username)
        else:
            client_socket.sendall(f"{target_character_name} is not online.\n".encode())

    elif cmd in ['reply', 'r']:
        last_tell_sender_username = account_manager.get_last_tell_sender(username)
        if not last_tell_sender_username:
            client_socket.sendall(b"No one has sent you a tell to reply to.\n")
            return
            
        message = ' '.join(args)
        target_username = last_tell_sender_username

        if target_username and account_manager.is_connected(target_username):
            target_character_name = account_manager.get_character_name(target_username)
            account_manager.send_message_to_client(target_username, 
                f"{COLOR_DARK_BLUE}{character['name']} replies: \"{message}\"{COLOR_RESET}\n")
            client_socket.sendall(
                f'{COLOR_DARK_BLUE}You reply to {target_character_name}: "{message}"{COLOR_RESET}\n'.encode())
        else:
            target_character_name = account_manager.get_character_name(target_username)
            client_socket.sendall(f"{target_character_name} is not online.\n".encode())

    elif cmd == 'broadcast':
        if character.get('account_level', 1) < ACCOUNT_LEVELS['admin']:
            client_socket.sendall(b"You don't have permission to use the broadcast command.\n")
            return
            
        message = ' '.join(args)
        broadcast_message = f"{COLOR_WHITE}(Admin) {character['name']} broadcasts: {message}{COLOR_RESET}\n"
        account_manager.broadcast_to_all_clients(broadcast_message)

    else:
        client_socket.sendall(b"Unknown chat command or insufficient privileges.\n")

def handle_movement(direction, character, client_socket, room_manager, item_manager, mob_manager, account_manager, username):
    direction_normalized = DIRECTION_ALIASES.get(direction.lower(), direction.lower())
    current_room_vnum = character.get('room')
    current_room = room_manager.get_room(current_room_vnum)

    if not current_room:
        client_socket.sendall(b"You are in an unknown place.\n")
        logging.error(f"Character '{character['name']}' is in an unknown room (vnum: {current_room_vnum}).")
        return

    exits = current_room.get('exits', {})
    exits_normalized = {key.lower(): value for key, value in exits.items()}

    if direction_normalized in exits_normalized:
        next_room_vnum = exits_normalized[direction_normalized]
        next_room = room_manager.get_room(next_room_vnum)

        if not next_room:
            client_socket.sendall(b"You can't go that way.\n")
            logging.error(f"Next room vnum '{next_room_vnum}' not found.")
            return

        # Remove player from current room
        removed = room_manager.remove_player_from_room(current_room_vnum, username)
        if removed:
            logging.debug(f"Player '{username}' removed from room {current_room_vnum} during movement.")
        else:
            logging.debug(f"Player '{username}' was not in room {current_room_vnum} when attempting to move.")

        # Add player to next room
        added = room_manager.add_player_to_room(next_room_vnum, username, character['name'])
        if added:
            logging.debug(f"Player '{username}' added to room {next_room_vnum} during movement.")
        else:
            logging.debug(f"Player '{username}' was already in room {next_room_vnum} during movement.")

        # Update character's room
        character['room'] = next_room_vnum
        account_manager.update_character(username, character)

        # Show the new room
        handle_look(character, client_socket, room_manager, item_manager, mob_manager, account_manager)
        logging.debug(f"Character '{character['name']}' moved to room {next_room_vnum}.")
    else:
        client_socket.sendall(b"You can't go that way.\n")
        logging.debug(f"Invalid movement direction '{direction}' for character '{character['name']}'.")

def handle_put(username, character, args, client_socket, room_manager, item_manager, account_manager):
    """Handle putting items into containers with LORE validation."""
    if not args:
        client_socket.sendall(b"Usage: put <item> in <container>\n")
        return

    # Parse the command
    command = ' '.join(args).lower()
    if 'in' not in command:
        client_socket.sendall(b"Usage: put <item> in <container>\n")
        return

    item_name, container_name = command.split(' in ', 1)
    item_name = item_name.strip()
    container_name = container_name.strip()

    # First, find the container
    container = None
    container_location = None  # 'inventory' or 'room'
    
    # Check inventory first
    inventory = character.get('inventory', [])
    for inv_item in inventory:
        if container_name in inv_item.get('name', '').lower() and inv_item.get('type') == 'containers':
            container = inv_item
            container_location = 'inventory'
            break

    # If not in inventory, check room
    if not container:
        current_room = room_manager.get_room(character['room'])
        if current_room:
            for room_item in current_room.get('items', []):
                if container_name in room_item.get('name', '').lower():
                    container = room_item
                    container_location = 'room'
                    break

    if not container:
        client_socket.sendall(f"You don't see '{container_name}' here.\n".encode())
        return

    # Check if container is locked
    if container.get('flags', {}).get('Locked', False):
        client_socket.sendall(b"That container is locked.\n")
        return

    # Find matching items in inventory
    matching_items = []
    for inv_item in inventory:
        if item_name in inv_item.get('name', '').lower():
            matching_items.append(inv_item)

    if not matching_items:
        client_socket.sendall(f"You don't have '{item_name}' in your inventory.\n".encode())
        return

    # If multiple matches, show numbered list
    if len(matching_items) > 1:
        response = "Which item do you want to put?\n"
        for i, item in enumerate(matching_items, 1):
            response += f"{i}. {item.get('name')}\n"
        client_socket.sendall(response.encode())
        return

    item_to_put = matching_items[0]

    # Check container capacity
    current_items = container.get('contents', [])
    if len(current_items) >= container.get('capacity', 10):
        client_socket.sendall(b"That container is full.\n")
        return

    # LORE item validation for containers
    if item_to_put.get('is_lore', False):
        # Count LORE items in container
        lore_count = sum(1 for content in current_items 
                        if content.get('vnum') == item_to_put.get('vnum') 
                        and content.get('is_lore', False))
        if lore_count > 0:
            client_socket.sendall(b"This container already has that LORE item.\n")
            return

    # Add item to container
    container.setdefault('contents', []).append(item_to_put)
    inventory.remove(item_to_put)

    # Update the container in its location
    if container_location == 'inventory':
        account_manager.update_character(username, character)
    else:  # container_location == 'room'
        room_manager.save_rooms()

    # Update item manager's LORE cache if needed
    if item_to_put.get('is_lore', False):
        item_manager.update_character_lore_cache(character)

    client_socket.sendall(f"You put {item_to_put.get('name')} in {container.get('name')}.\n".encode())

def handle_lock(username, character, args, client_socket, room_manager, item_manager, account_manager):
    """Handle locking containers."""
    if not args:
        client_socket.sendall(b"What do you want to lock?\n")
        return

    container_name = ' '.join(args).lower()
    
    # Find the container
    container = None
    container_location = None
    inventory = character.get('inventory', [])
    
    # Check inventory
    for inv_item in inventory:
        if container_name in inv_item.get('name', '').lower() and inv_item.get('type') == 'containers':
            container = inv_item
            container_location = 'inventory'
            break

    # Check room
    if not container:
        current_room = room_manager.get_room(character['room'])
        if current_room:
            for room_item in current_room.get('items', []):
                base_item = item_manager.get_item_by_vnum(room_item.get('vnum'), room_item.get('type'))
                if (base_item and container_name in base_item.get('name', '').lower() 
                    and base_item.get('type') == 'containers'):
                    container = room_item
                    container_location = 'room'
                    break

    if not container:
        client_socket.sendall(f"You don't see '{container_name}' here.\n".encode())
        return

    # Check if container can be locked
    if not container.get('flags', {}).get('Closeable', False):
        client_socket.sendall(b"That cannot be locked.\n")
        return

    # Check if already locked
    if container.get('flags', {}).get('Locked', False):
        client_socket.sendall(b"It's already locked.\n")
        return

    # Check if a key is required and if player has it
    if container.get('flags', {}).get('Key_Required', False):
        key_name = container.get('key_name')
        has_key = False
        for inv_item in inventory:
            if inv_item.get('type') == 'keys' and inv_item.get('key_name') == key_name:
                has_key = True
                break
        
        if not has_key:
            client_socket.sendall(b"You don't have the right key.\n")
            return

    # Lock the container
    container['flags']['Locked'] = True
    
    # Update the container in its location
    if container_location == 'inventory':
        account_manager.update_character(username, character)
    else:  # container_location == 'room'
        room_manager.save_rooms()

    client_socket.sendall(f"You lock {container.get('name')}.\n".encode())

def handle_unlock(username, character, args, client_socket, room_manager, item_manager, account_manager):
    """Handle unlocking containers."""
    if not args:
        client_socket.sendall(b"What do you want to unlock?\n")
        return

    container_name = ' '.join(args).lower()
    
    # Find the container
    container = None
    container_location = None
    inventory = character.get('inventory', [])
    
    # Check inventory
    for inv_item in inventory:
        if container_name in inv_item.get('name', '').lower() and inv_item.get('type') == 'containers':
            container = inv_item
            container_location = 'inventory'
            break

    # Check room
    if not container:
        current_room = room_manager.get_room(character['room'])
        if current_room:
            for room_item in current_room.get('items', []):
                base_item = item_manager.get_item_by_vnum(room_item.get('vnum'), room_item.get('type'))
                if (base_item and container_name in base_item.get('name', '').lower() 
                    and base_item.get('type') == 'containers'):
                    container = room_item
                    container_location = 'room'
                    break

    if not container:
        client_socket.sendall(f"You don't see '{container_name}' here.\n".encode())
        return

    # Check if locked
    if not container.get('flags', {}).get('Locked', False):
        client_socket.sendall(b"It's not locked.\n")
        return

    # Check if a key is required and if player has it
    if container.get('flags', {}).get('Key_Required', False):
        key_name = container.get('key_name')
        has_key = False
        for inv_item in inventory:
            if inv_item.get('type') == 'keys' and inv_item.get('key_name') == key_name:
                has_key = True
                break
        
        if not has_key:
            client_socket.sendall(b"You don't have the right key.\n")
            return

    # Unlock the container
    container['flags']['Locked'] = False
    
    # Update the container in its location
    if container_location == 'inventory':
        account_manager.update_character(username, character)
    else:  # container_location == 'room'
        room_manager.save_rooms()

    client_socket.sendall(f"You unlock {container.get('name')}.\n".encode())

def find_corpse_in_room(corpse_name, room, room_manager):
    """
    Finds a corpse in the given room by its name.
    """
    for item in room.get('items', []):
        if item.get('vnum') == 'corpse' and corpse_name in item.get('name', '').lower():
            logging.debug(f"Found corpse '{corpse_name}' in room '{room.get('name', 'Unknown')}'.")
            return item
    logging.debug(f"Corpse '{corpse_name}' not found in room '{room.get('name', 'Unknown')}'.")
    return None

def handle_get(username, character, args, client_socket, room_manager, item_manager, account_manager):
    """Handle getting items from room or containers with proper flag validation."""
    if not args:
        client_socket.sendall(b"Get what?\n")
        return

    # Parse arguments
    if len(args) >= 3 and args[1].lower() == 'from':
        item_name = args[0].lower()
        container_name = ' '.join(args[2:]).lower()
    elif len(args) >= 4 and args[0].lower() == 'all' and args[1].lower() == 'from':
        item_name = 'all'
        container_name = ' '.join(args[3:]).lower()
    else:
        item_name = ' '.join(args).lower()
        container_name = None

    current_room = room_manager.get_room(character.get('room'))
    if not current_room:
        client_socket.sendall(b"You are in an unknown place.\n")
        return

    # Handle getting from container
    if container_name:
        # Find container in inventory first
        container = None
        container_location = None
        inventory = character.get('inventory', [])
        
        for inv_item in inventory:
            if container_name in inv_item.get('name', '').lower() and inv_item.get('type') == 'containers':
                container = inv_item
                container_location = 'inventory'
                break

        # If not in inventory, check room
        if not container:
            for room_item in current_room.get('items', []):
                if ((room_item.get('type') == 'corpses' and 'corpse' in container_name.lower()) or
                    (container_name in room_item.get('name', '').lower())):
                    container = room_item
                    container_location = 'room'
                    break

        if not container:
            client_socket.sendall(f"You don't see '{container_name}' here.\n".encode())
            return

        # Check if container is locked
        if container.get('flags', {}).get('Locked', False) and container.get('type') != 'corpses':
            client_socket.sendall(b"That container is locked.\n")
            return

        # Check if container is immobile and in the room
        if (container_location == 'room' and 
            (container.get('immobile', False) or container.get('flags', {}).get('Immobile', False))):
            client_socket.sendall(b"That container cannot be moved.\n")
            return

        if not container.get('contents', []):
            client_socket.sendall(f"The {container.get('name', 'container')} is empty.\n".encode())
            return

        # Check corpse ownership
        if container.get('type') == 'corpses' and container.get('killed_by') != username:
            client_socket.sendall(b"That is not your kill.\n")
            return

        # Get all items or specific item
        contents = container.get('contents', [])
        if item_name == 'all':
            items_to_get = contents[:]
        else:
            items_to_get = []
            for content in contents:
                base_item = item_manager.get_item_by_vnum(content.get('vnum'), content.get('type'))
                if base_item and item_name in base_item.get('name', '').lower():
                    items_to_get.append(content)

        if not items_to_get:
            client_socket.sendall(f"You don't see '{item_name}' in the {container.get('name', 'container')}.\n".encode())
            return

        # Process items - now with LORE checking and No_Take flag checking
        for item in items_to_get[:]:
            if item.get('vnum') == 'gold':
                gold_amount = item.get('quantity', 0)
                character['gold'] = character.get('gold', 0) + gold_amount
                client_socket.sendall(f"You get {gold_amount} gold coins from {container.get('name')}.\n".encode())
            else:
                base_item = item_manager.get_item_by_vnum(item.get('vnum'), item.get('type'))
                if base_item:
                    # Check No_Take flag
                    if base_item.get('flags', {}).get('No_Take', False) or item.get('flags', {}).get('No_Take', False):
                        client_socket.sendall(f"That doesn't belong to you.\n".encode())
                        continue

                    # Check LORE restrictions
                    if base_item.get('is_lore', False):
                        can_acquire = item_manager.can_acquire_lore_item(character, base_item)
                        if not can_acquire:
                            client_socket.sendall(f"You already have a LORE item: {base_item['name']}.\n".encode())
                            continue
                            
                    inv_entry = copy.deepcopy(base_item)
                    inv_entry.update({
                        'quantity': item.get('quantity', 1),
                        'name': item.get('custom_name', base_item.get('name')),
                        'type': item.get('type', base_item.get('type'))
                    })
                    character.setdefault('inventory', []).append(inv_entry)
                    client_socket.sendall(f"You get {inv_entry['name']} from {container.get('name')}.\n".encode())
                else:
                    logging.error(f"Could not find base item data for vnum {item.get('vnum')}")
                    continue

            contents.remove(item)

        # Remove empty corpse
        if not contents and container.get('type') == 'corpses':
            current_room['items'].remove(container)
        else:
            container['contents'] = contents

        # Save changes
        if container_location == 'inventory':
            account_manager.update_character(username, character)
        room_manager.save_rooms()
        account_manager.update_character(username, character)

    else:
        # Getting items directly from room
        room_items = current_room.get('items', [])
        
        # Handle 'get all'
        if item_name == 'all':
            if not room_items:
                client_socket.sendall(b"There is nothing here to get.\n")
                return
            
            items_to_get = []
            for item in room_items:
                # Skip corpses and check both immobile and No_Take flags
                if (item.get('type') == 'corpses' or 
                    item.get('immobile', False) or 
                    item.get('flags', {}).get('Immobile', False) or
                    item.get('flags', {}).get('No_Take', False)):
                    continue
                    
                # Check the base item flags as well
                base_item = item_manager.get_item_by_vnum(item.get('vnum'), item.get('type'))
                if base_item and base_item.get('flags', {}).get('No_Take', False):
                    continue
                    
                items_to_get.append(item)
                
            if not items_to_get:
                client_socket.sendall(b"There is nothing here you can get.\n")
                return
        else:
            # Find specific item
            items_to_get = []
            for item in room_items:
                # Skip corpses for direct getting
                if item.get('type') == 'corpses':
                    continue

                # Check if the item's name matches
                base_item = item_manager.get_item_by_vnum(item.get('vnum'), item.get('type'))
                if ((item_name in item.get('name', '').lower()) or 
                    (base_item and item_name in base_item.get('name', '').lower())):
                    # Check both instance and base item flags
                    if (item.get('immobile', False) or 
                        item.get('flags', {}).get('Immobile', False) or
                        item.get('flags', {}).get('No_Take', False) or
                        (base_item and base_item.get('flags', {}).get('No_Take', False))):
                        client_socket.sendall(b"That doesn't belong to you.\n")
                        return
                    items_to_get.append(item)

            if not items_to_get:
                client_socket.sendall(f"You don't see '{item_name}' here.\n".encode())
                return

        # Process each item - now with LORE checking
        for item in items_to_get[:]:
            if item.get('vnum') == 'gold':
                gold_amount = item.get('quantity', 0)
                character['gold'] = character.get('gold', 0) + gold_amount
                client_socket.sendall(f"You pick up {gold_amount} gold coins.\n".encode())
            else:
                # Check LORE restrictions
                if item.get('is_lore', False):
                    can_acquire = item_manager.can_acquire_lore_item(character, item)
                    if not can_acquire:
                        client_socket.sendall(f"You already have a LORE item: {item['name']}.\n".encode())
                        continue

                # Create inventory entry
                inv_entry = copy.deepcopy(item)
                inv_entry['quantity'] = item.get('quantity', 1)
                character.setdefault('inventory', []).append(inv_entry)
                client_socket.sendall(f"You pick up {item.get('name')}.\n".encode())

            # Remove item from room
            room_items.remove(item)

        # Save changes
        room_manager.save_rooms()
        account_manager.update_character(username, character)

def handle_drop(username, character, args, client_socket, room_manager, item_manager, account_manager):
    """Handle dropping items and currency."""
    if not args:
        client_socket.sendall(b"Usage: drop <item_name> or drop <amount> gold\n")
        return

    # Check for currency drop format (e.g., "drop 50 gold")
    try:
        parts = ' '.join(args).lower().split()
        if len(parts) >= 2 and parts[-1] == 'gold':
            # Try to parse the amount
            try:
                amount = int(''.join(parts[:-1]))  # Join all parts except 'gold' in case of "drop 1 2 3 gold"
                if amount <= 0:
                    client_socket.sendall(b"Amount must be positive.\n")
                    return
                
                # Check if player has enough gold
                player_gold = character.get('gold', 0)
                if amount > player_gold:
                    client_socket.sendall(f"You only have {player_gold} gold.\n".encode())
                    return
                
                # Create gold entry for room
                gold_entry = {
                    'vnum': 'gold',
                    'name': f"{amount} gold coins",
                    'type': 'currency',
                    'quantity': amount,
                    'short_desc': f"{amount} gold coins lie here",
                    'long_desc': f"A pile of {amount} gold coins."
                }
                
                # Add to room and subtract from player
                room_vnum = character['room']
                success = room_manager.add_item_to_room(room_vnum, gold_entry)
                
                if success:
                    character['gold'] -= amount
                    account_manager.update_character(username, character)
                    client_socket.sendall(f"You drop {amount} gold coins.\n".encode())
                    logging.info(f"Character '{character['name']}' dropped {amount} gold in room {room_vnum}.")
                else:
                    client_socket.sendall(b"Error: Could not drop the gold.\n")
                return
                
            except ValueError:
                client_socket.sendall(b"Invalid amount specified.\n")
                return
    except Exception as e:
        logging.error(f"Error processing currency drop: {e}")
        client_socket.sendall(b"Error processing drop command.\n")
        return

    # Handle normal item dropping
    item_name = ' '.join(args).lower()
    inventory = character.get('inventory', [])
    item = next((i for i in inventory if item_name in i.get('name', '').lower()), None)

    if item:
        # Create a complete item entry with all required fields
        item_entry = {
            'vnum': item['vnum'],
            'name': item['name'],
            'quantity': 1,
            'type': item.get('type', 'item'),
            'short_desc': item.get('short_desc', ''),
            'long_desc': item.get('long_desc', ''),
            'flags': item.get('flags', {}),  # Include flags for containers
            'key_name': item.get('key_name', ''),  # Include key_name if it's a container
            'capacity': item.get('capacity', 0),  # Include capacity if it's a container
            'contents': item.get('contents', [])  # Include contents if it's a container
        }

        if item.get('type') == 'containers':
            if item.get('contents', []):
                client_socket.sendall(b"You should empty the container first.\n")
                return

        inventory.remove(item)
        room_vnum = character['room']
        success = room_manager.add_item_to_room(room_vnum, item_entry)
        if success:
            account_manager.update_character(username, character)
            client_socket.sendall(f"You drop {item.get('name')} on the ground.\n".encode())
            logging.info(f"Character '{character['name']}' dropped '{item['name']}' in room {room_vnum}.")
        else:
            # If drop fails, put the item back in inventory
            inventory.append(item)
            client_socket.sendall(b"Error: Could not drop the item in the room.\n")
    else:
        client_socket.sendall(f"You don't have '{item_name}' in your inventory.\n".encode())

def handle_examine(character, args, client_socket, room_manager, item_manager, mob_manager):
    """Handle examining objects, creatures, and inventory items."""
    if not args:
        client_socket.sendall(b"What do you want to examine?\n")
        return

    target_name = ' '.join(args).lower()
    current_room = room_manager.get_room(character['room'])

    if not current_room:
        client_socket.sendall(b"You are in an unknown place.\n")
        return

    # First check inventory items
    inventory = character.get('inventory', [])
    for item in inventory:
        if target_name in item.get('name', '').lower():
            response = item.get('long_desc', 'You see nothing special.')
            
            # Add special handling for containers
            if item.get('type') == 'containers':
                if item.get('flags', {}).get('Locked', False):
                    response += "\nIt is currently locked."
                else:
                    contents = item.get('contents', [])
                    if contents:
                        response += "\nContents:"
                        for content in contents:
                            content_item = item_manager.get_item_by_vnum(content['vnum'], content['type'])
                            if content_item:
                                response += f"\n- {content_item['name']}"
                    else:
                        response += "\nIt is empty."
            
            # Add stats information for equipment
            if 'stats' in item:
                response += "\nStats:"
                for stat, value in item['stats'].items():
                    response += f"\n{stat}: {value:+d}"
                    
            # Add damage information for weapons
            if item.get('type') == 'weapons':
                response += f"\nDamage: {item.get('min_damage', 1)}-{item.get('max_damage', 3)}"
            
            # Add flags information
            flags = []
            if item.get('is_lore', False):
                flags.append("LORE")
            if item.get('is_no_rent', False):
                flags.append("NO-RENT")
            if flags:
                response += f"\nFlags: {', '.join(flags)}"
                
            client_socket.sendall(response.encode() + b"\n")
            return

    # Check equipped items
    equipment = character.get('equipment', {})
    for slot, equipped_item in equipment.items():
        if equipped_item and target_name in equipped_item.get('name', '').lower():
            response = equipped_item.get('long_desc', 'You see nothing special.')
            
            # Add stats information
            if 'stats' in equipped_item:
                response += "\nStats:"
                for stat, value in equipped_item['stats'].items():
                    response += f"\n{stat}: {value:+d}"
                    
            # Add damage information for weapons
            if equipped_item.get('type') == 'weapons':
                response += f"\nDamage: {equipped_item.get('min_damage', 1)}-{equipped_item.get('max_damage', 3)}"
            
            # Add equipment slot information
            response += f"\nEquipped on: {slot}"
            
            # Add flags information
            flags = []
            if equipped_item.get('is_lore', False):
                flags.append("LORE")
            if equipped_item.get('is_no_rent', False):
                flags.append("NO-RENT")
            if flags:
                response += f"\nFlags: {', '.join(flags)}"
                
            client_socket.sendall(response.encode() + b"\n")
            return

    # Then check mobs (prioritize mobs over room items)
    for mob_entry in current_room.get('mobs', []):
        if mob_entry.get('is_template', False):
            continue
        mob = mob_manager.get_mob_by_vnum(mob_entry['vnum'])
        if mob and target_name in mob.get('name', '').lower():
            description = (mob.get('description') or 
                         mob.get('long_desc') or 
                         mob.get('short_desc', 'You see nothing special.'))
            client_socket.sendall(f"{description}\n".encode())
            
            # Add stats for more detail
            stats = mob.get('stats', {})
            if stats:
                stats_text = "\nStats:"
                for stat, value in stats.items():
                    if stat.startswith('Max_'):
                        continue
                    stats_text += f"\n{stat}: {value}"
                client_socket.sendall(stats_text.encode() + b"\n")
            return

    # Finally check room items
    for item_entry in current_room.get('items', []):
        # Special handling for corpses
        if item_entry.get('type') == 'corpses' and 'corpse' in target_name:
            handle_corpse_examine(item_entry, client_socket, item_manager)
            return

        # Handle containers in room
        base_item = item_manager.get_item_by_vnum(item_entry.get('vnum'), item_entry.get('type'))
        if base_item and target_name in base_item.get('name', '').lower():
            response = base_item.get('long_desc', 'You see nothing special.')
            if item_entry.get('type') == 'containers':
                if item_entry.get('flags', {}).get('Locked', False):
                    response += "\nIt is currently locked."
                elif not item_entry.get('flags', {}).get('Locked', False):
                    contents = item_entry.get('contents', [])
                    if contents:
                        response += "\nContents:"
                        for content in contents:
                            content_item = item_manager.get_item_by_vnum(content['vnum'], content['type'])
                            if content_item:
                                response += f"\n- {content_item['name']}"
                    else:
                        response += "\nIt is empty."
            elif 'stats' in base_item:
                response += "\nStats:"
                for stat, value in base_item['stats'].items():
                    response += f"\n{stat}: {value:+d}"
                    
            # Add flags information for room items
            flags = []
            if base_item.get('is_lore', False):
                flags.append("LORE")
            if base_item.get('is_no_rent', False):
                flags.append("NO-RENT")
            if base_item.get('immobile', False):
                flags.append("IMMOBILE")
            if base_item.get('no_take', False):
                flags.append("NO-TAKE")
            if flags:
                response += f"\nFlags: {', '.join(flags)}"
                
            client_socket.sendall(response.encode() + b"\n")
            return

    client_socket.sendall(f"You don't see '{target_name}' here or in your inventory.\n".encode())

def handle_corpse_examine(corpse, client_socket, item_manager):
    """Helper function to handle corpse examination."""
    response_parts = [corpse['long_desc']]
    
    contents = corpse.get('contents', [])
    if not contents:
        response_parts.append("The corpse is empty.")
    else:
        response_parts.append("Contents:")
        content_groups = {}
        
        for content in contents:
            if content.get('vnum') == 'gold':
                quantity = content.get('quantity', 0)
                response_parts.append(f"  {quantity} gold coins")
                continue
            
            base_item = item_manager.get_item_by_vnum(content.get('vnum'), content.get('type'))
            if base_item:
                key = (base_item.get('name'), content.get('type'))
                if key not in content_groups:
                    content_groups[key] = {
                        'name': base_item.get('name'),
                        'quantity': 0
                    }
                content_groups[key]['quantity'] += content.get('quantity', 1)
        
        for item_data in content_groups.values():
            if item_data['quantity'] > 1:
                response_parts.append(f"  {item_data['name']} x{item_data['quantity']}")
            else:
                response_parts.append(f"  {item_data['name']}")

    client_socket.sendall('\n'.join(response_parts).encode() + b'\n')

def handle_equip(username, character, args, client_socket, room_manager, item_manager, account_manager):
    """Handle equipment with LORE validation."""
    if not args:
        client_socket.sendall(b"Usage: wear|wield|equip|brandish <item_name>\n")
        return

    item_name = ' '.join(args).lower()
    inventory = character.get('inventory', [])
    item = next((i for i in inventory if item_name in i.get('name', '').lower()), None)

    if not item:
        client_socket.sendall(f"You don't have '{item_name}' in your inventory.\n".encode())
        return

    # Check LORE restrictions before equipping
    if item.get('is_lore', False):
        # Check equipped items for LORE item
        equipment = character.get('equipment', {})
        for slot, equipped_item in equipment.items():
            if equipped_item and equipped_item.get('vnum') == item.get('vnum') and equipped_item.get('is_lore', False):
                client_socket.sendall(f"You already have that LORE item equipped.\n".encode())
                return

    item_type = item.get('type', '').lower()
    if item_type == 'armors':
        # Get the slot and convert to lowercase for comparison
        slot = item.get('slot', '')
        if not slot:
            client_socket.sendall(b"This armor cannot be equipped.\n")
            return
            
        # Convert slot to lowercase for equipment dictionary lookup
        slot_lower = slot.lower()
        
        # Initialize equipment slots if they don't exist
        if 'equipment' not in character:
            character['equipment'] = {}
            
        # Ensure all standard equipment slots exist
        standard_slots = ['head', 'neck', 'chest', 'waist', 'legs', 'feet', 'hands', 'ring1', 'ring2', 'mainhand', 'offhand', 'light_source']
        for std_slot in standard_slots:
            if std_slot not in character['equipment']:
                character['equipment'][std_slot] = None

        # Map armor slots to equipment slots
        slot_mapping = {
            'head': 'head',
            'neck': 'neck',
            'chest': 'chest',
            'waist': 'waist',
            'legs': 'legs',
            'feet': 'feet',
            'hands': 'hands',
            'ring': 'ring1'  # Default to first ring slot
        }

        # Get the correct equipment slot
        equip_slot = slot_mapping.get(slot_lower)
        if not equip_slot:
            client_socket.sendall(f"Invalid equipment slot '{slot}' for this armor.\n".encode())
            return

        # Special handling for LORE rings
        if slot_lower == 'ring' and item.get('is_lore', False):
            ring1 = character['equipment'].get('ring1')
            ring2 = character['equipment'].get('ring2')
            
            # Check if either ring slot has the same LORE item
            if (ring1 and ring1.get('vnum') == item.get('vnum') and ring1.get('is_lore', False)) or \
               (ring2 and ring2.get('vnum') == item.get('vnum') and ring2.get('is_lore', False)):
                client_socket.sendall(b"You already have that LORE ring equipped.\n")
                return

            # Determine which ring slot to use
            if ring1 is None:
                equip_slot = 'ring1'
            elif ring2 is None:
                equip_slot = 'ring2'
            else:
                client_socket.sendall(b"You have no free ring slots.\n")
                return
        elif slot_lower == 'ring':
            if character['equipment']['ring1'] is None:
                equip_slot = 'ring1'
            elif character['equipment']['ring2'] is None:
                equip_slot = 'ring2'
            else:
                client_socket.sendall(b"You have no free ring slots.\n")
                return

        # Check if slot is already occupied
        if character['equipment'].get(equip_slot) is not None:
            client_socket.sendall(f"You already have something equipped in the '{slot}' slot.\n".encode())
            return

        # Equip the item
        character['equipment'][equip_slot] = item
        inventory.remove(item)

        # Update total stats
        calculate_total_stats(character)
        account_manager.update_character(username, character)
        
        # Update LORE cache if needed
        if item.get('is_lore', False):
            item_manager.update_character_lore_cache(character)
        
        client_socket.sendall(f"You equip {item.get('name')} on your {slot}.\n".encode())
        logging.info(f"Character '{character['name']}' equipped '{item['name']}' in {equip_slot}")

    elif item_type == 'weapons':
        handle_weapon_equip(username, character, item, client_socket, account_manager, item_manager)
    else:
        client_socket.sendall(b"You can't equip that item.\n")

    # Ensure the character data is saved after equipping
    account_manager.update_character(username, character)

def handle_weapon_equip(username, character, item, client_socket, account_manager, item_manager):
    """Handle weapon equipping with LORE validation."""
    # Check for LORE weapon restrictions
    if item.get('is_lore', False):
        # Check both weapon slots for same LORE weapon
        mainhand = character['equipment'].get('mainhand')
        offhand = character['equipment'].get('offhand')
        
        if (mainhand and mainhand.get('vnum') == item.get('vnum') and mainhand.get('is_lore', False)) or \
           (offhand and offhand.get('vnum') == item.get('vnum') and offhand.get('is_lore', False)):
            client_socket.sendall(b"You already have that LORE weapon equipped.\n")
            return

    if character['equipment'].get('mainhand') is None:
        character['equipment']['mainhand'] = item
        character['inventory'].remove(item)
        calculate_total_stats(character)
        
        # Update LORE cache if needed
        if item.get('is_lore', False):
            item_manager.update_character_lore_cache(character)
            
        account_manager.update_character(username, character)
        client_socket.sendall(f"You wield {item.get('name')} in your main hand.\n".encode())
        logging.info(f"Character '{character['name']}' wielded '{item['name']}' in main hand.")
    elif character['equipment'].get('offhand') is None:
        character['equipment']['offhand'] = item
        character['inventory'].remove(item)
        calculate_total_stats(character)
        
        # Update LORE cache if needed
        if item.get('is_lore', False):
            item_manager.update_character_lore_cache(character)
            
        account_manager.update_character(username, character)
        client_socket.sendall(f"You wield {item.get('name')} in your off hand.\n".encode())
        logging.info(f"Character '{character['name']}' wielded '{item['name']}' in off hand.")
    else:
        client_socket.sendall(b"Both your hands are occupied.\n")

def handle_unequip(username, character, args, client_socket, room_manager, item_manager, account_manager):
    if not args:
        client_socket.sendall(b"Usage: unequip|remove <item_name>\n")
        return

    item_name = ' '.join(args).lower()
    equipment = character.get('equipment', {})
    found = False

    for slot, item in equipment.items():
        if item and item_name in item.get('name', '').lower():
            character['inventory'].append(item)
            equipment[slot] = None

            # Recalculate stats after unequipping
            calculate_total_stats(character)

            account_manager.update_character(username, character)
            client_socket.sendall(f"You unequip {item.get('name')} from your {slot}.\n".encode())
            logging.info(f"Character '{character['name']}' unequipped '{item.get('name')}' from {slot}.")
            found = True
            break

    if not found:
        client_socket.sendall(f"You are not wearing or wielding '{item_name}'.\n".encode())

def handle_inventory(character, client_socket):
    # Display gold
    gold_amount = character.get('gold', 0)
    
    # Start with displaying the gold amount
    inv_desc = f"You currently have {gold_amount} gold coins.\n"

    # Display items in inventory
    inventory = character.get('inventory', [])
    if inventory:
        inv_desc += "Your inventory contains:\n"
        item_groups = {}
        
        for item in inventory:
            item_name = item.get('name', 'Unknown')
            item_type = item.get('type', 'misc')
            quantity = item.get('quantity', 1)
            
            # Group items by name and type
            key = (item_name, item_type)
            if key not in item_groups:
                item_groups[key] = {
                    'name': item_name,
                    'quantity': 0,
                    'type': item_type
                }
            item_groups[key]['quantity'] += quantity
        
        # Display grouped items
        for item_data in item_groups.values():
            if item_data['type'] == 'containers':
                contents = next((item for item in inventory if item.get('name') == item_data['name']), {}).get('contents', [])
                if contents:
                    inv_desc += f"- {item_data['name']} (contains items)"
                else:
                    inv_desc += f"- {item_data['name']} (empty)"
                if item_data['quantity'] > 1:
                    inv_desc += f" x{item_data['quantity']}"
                inv_desc += "\n"
            else:
                if item_data['quantity'] > 1:
                    inv_desc += f"- {item_data['name']} x{item_data['quantity']}\n"
                else:
                    inv_desc += f"- {item_data['name']}\n"
    else:
        inv_desc += "Your inventory is empty.\n"

    # Send the inventory description to the player
    client_socket.sendall(inv_desc.encode())

def find_matching_consumables(character, name, consumable_type=None):
    """
    Find all consumables in character's inventory matching the name and type.
    """
    matching_items = []
    for item in character.get('inventory', []):
        if item.get('type') != 'consumables':
            continue
            
        item_name = item.get('name', '').lower()
        if name.lower() in item_name:
            if consumable_type is None or item.get('consumable_type', '').lower() == consumable_type.lower():
                matching_items.append(item)
    
    return matching_items

def handle_use(command, username, character, client_socket, room_manager, item_manager, mob_manager, account_manager, skill_manager):
    """
    Enhanced handle_use function that supports consumables.
    Usage:
        use skill <skill_name> [<target>]
        use item <item_name>
        use <item_name>  # Shortcut for use item
    """
    parts = command.split()
    if len(parts) < 2:
        client_socket.sendall(b"What would you like to use?\n")
        return

    use_type = parts[1].lower()
    
    # Handle 'use item' or direct 'use' command
    if use_type == 'item' or parts[0].lower() == 'use':
        target = ' '.join(parts[2:]) if use_type == 'item' else ' '.join(parts[1:])
        matching_items = find_matching_consumables(character, target)
        
        if not matching_items:
            client_socket.sendall(f"You don't have any usable items named '{target}'.\n".encode())
            return
            
        if len(matching_items) > 1:
            response = "Which would you like to use?\n"
            for i, item in enumerate(matching_items, 1):
                response += f"{i}. {item.get('name')}\n"
            client_socket.sendall(response.encode())
            return
            
        item = matching_items[0]
        consumable_type = item.get('consumable_type', '').lower()
        
        if consumable_type == 'food':
            handle_eat(username, character, [item.get('name')], client_socket, account_manager)
        elif consumable_type in ['drink', 'potion']:
            handle_drink(username, character, [item.get('name')], client_socket, account_manager)
        else:
            client_socket.sendall(f"You can't figure out how to use {item.get('name')}.\n".encode())
            
    # Handle 'use skill' command
    elif use_type == 'skill':
        if len(parts) < 3:
            client_socket.sendall(b"Which skill would you like to use?\n")
            return
            
        skill_name = ' '.join(parts[2:])
        skill = skill_manager.get_skill(character.get('class', 'wanderer'), skill_name)
        
        if skill:
            execute_skill(skill, character, client_socket, account_manager)
            account_manager.update_character(username, character)
        else:
            client_socket.sendall(f"You don't know the skill '{skill_name}'.\n".encode())
            
    else:
        client_socket.sendall(b"Invalid usage. Use 'use <item_name>' or 'use skill <name>'.\n")

def handle_eat(username, character, args, client_socket, account_manager):
    """Handle eating food items."""
    if not args:
        client_socket.sendall(b"What would you like to eat?\n")
        return

    item_name = ' '.join(args).lower()
    matching_food = find_matching_consumables(character, item_name, 'food')

    if not matching_food:
        client_socket.sendall(f"You don't have any food named '{item_name}'.\n".encode())
        return

    if len(matching_food) > 1:
        response = "Which would you like to eat?\n"
        for i, food in enumerate(matching_food, 1):
            response += f"{i}. {food.get('name')}\n"
        client_socket.sendall(response.encode())
        return

    food = matching_food[0]
    
    # Check if already at max HP
    if character['stats']['HP'] >= character['stats']['Max_HP']:
        client_socket.sendall(f"You're already at full health.\n".encode())
        return

    # Apply healing effect
    heal_amount = min(
        food.get('effect_value', 10),
        character['stats']['Max_HP'] - character['stats']['HP']
    )
    character['stats']['HP'] += heal_amount

    # Remove item if all uses are consumed
    uses_left = food.get('uses', 1) - 1
    if uses_left <= 0:
        character['inventory'].remove(food)
    else:
        food['uses'] = uses_left

    # Save character changes
    account_manager.update_character(username, character)
    
    client_socket.sendall(
        f"You eat {food.get('name')} and restore {heal_amount} HP.\n".encode()
    )

def handle_drink(username, character, args, client_socket, account_manager):
    """Handle drinking potions and other beverages."""
    if not args:
        client_socket.sendall(b"What would you like to drink?\n")
        return

    item_name = ' '.join(args).lower()
    matching_drinks = find_matching_consumables(character, item_name, consumable_type=None)
    matching_drinks = [item for item in matching_drinks 
                      if item.get('consumable_type', '').lower() in ['drink', 'potion']]

    if not matching_drinks:
        client_socket.sendall(f"You don't have any drinks named '{item_name}'.\n".encode())
        return

    if len(matching_drinks) > 1:
        response = "Which would you like to drink?\n"
        for i, drink in enumerate(matching_drinks, 1):
            response += f"{i}. {drink.get('name')}\n"
        client_socket.sendall(response.encode())
        return

    drink = matching_drinks[0]
    effect_type = drink.get('effect_type', '').lower()
    effect_value = drink.get('effect_value', 0)
    
    # Handle different potion effects
    message = ""
    applied_effect = False
    
    if effect_type == 'heal':
        if character['stats']['HP'] >= character['stats']['Max_HP']:
            client_socket.sendall(f"You're already at full health.\n".encode())
            return
        
        heal_amount = min(
            effect_value,
            character['stats']['Max_HP'] - character['stats']['HP']
        )
        character['stats']['HP'] += heal_amount
        message = f"You drink {drink.get('name')} and restore {heal_amount} HP."
        applied_effect = True
        
    elif effect_type == 'restore sp':
        if character['stats']['SP'] >= character['stats']['Max_SP']:
            client_socket.sendall(f"Your skill points are already full.\n".encode())
            return
            
        restore_amount = min(
            effect_value,
            character['stats']['Max_SP'] - character['stats']['SP']
        )
        character['stats']['SP'] += restore_amount
        message = f"You drink {drink.get('name')} and restore {restore_amount} SP."
        applied_effect = True
        
    elif effect_type == 'restore ap':
        if character['stats']['AP'] >= character['stats']['Max_AP']:
            client_socket.sendall(f"Your ability points are already full.\n".encode())
            return
            
        restore_amount = min(
            effect_value,
            character['stats']['Max_AP'] - character['stats']['AP']
        )
        character['stats']['AP'] += restore_amount
        message = f"You drink {drink.get('name')} and restore {restore_amount} AP."
        applied_effect = True
        
    else:
        message = f"You drink {drink.get('name')}."
        applied_effect = True

    if applied_effect:
        # Remove item if all uses are consumed
        uses_left = drink.get('uses', 1) - 1
        if uses_left <= 0:
            character['inventory'].remove(drink)
        else:
            drink['uses'] = uses_left
            
        # Save character changes
        account_manager.update_character(username, character)
        
    client_socket.sendall(f"{message}\n".encode())

def execute_skill(skill, character, client_socket, account_manager, target=None, room_manager=None, mob_manager=None, item_manager=None):
    """
    Executes the given skill for the character.
    Checks for cooldowns and SP availability before execution.
    Integrates with the combat system based on the skill's effect.
    """
    skill_name = skill.get('name', 'Unknown Skill').lower()
    current_time = time.time()
    cooldown = skill.get('cooldown', 5)       # Cooldown in seconds
    sp_cost = skill.get('sp_cost', 0)         # Skill Points cost

    # Initialize skill cooldowns if not present
    if 'skill_cooldowns' not in character:
        character['skill_cooldowns'] = {}

    # Check if skill is on cooldown
    last_used = character['skill_cooldowns'].get(skill_name, 0)
    if current_time - last_used < cooldown:
        remaining = int(cooldown - (current_time - last_used))
        client_socket.sendall(f"Skill '{skill.get('name')}' is on cooldown for {remaining} more seconds.\n".encode())
        logging.info(f"Character '{character['name']}' attempted to use skill '{skill.get('name')}' which is on cooldown for {remaining} more seconds.")
        return

    # Check if character has enough SP
    if character.get('sp', 0) < sp_cost:
        client_socket.sendall(f"Not enough SP to use '{skill.get('name')}'. Required: {sp_cost}, Current: {character.get('sp', 0)}\n".encode())
        logging.info(f"Character '{character['name']}' has insufficient SP to use skill '{skill.get('name')}'. Required: {sp_cost}, Current: {character.get('sp', 0)}.")
        return

    # Deduct SP cost
    character['sp'] -= sp_cost
    logging.debug(f"Character '{character['name']}' used {sp_cost} SP to execute skill '{skill.get('name')}'. Remaining SP: {character['sp']}.")

    # Update last used time
    character['skill_cooldowns'][skill_name] = current_time

    # Execute skill effects based on 'effect' type
    effect = skill.get('effect', '')
    value = skill.get('value', 0)

    try:
        if effect == 'damage':
            if not target:
                client_socket.sendall(b"Usage: use skill <skill_name> <target>\n")
                logging.warning(f"Skill '{skill.get('name')}' requires a target but none was provided by '{character['name']}'.")
                return
            # Implement damage to a specific target
            handle_skill_damage(skill, character, client_socket, account_manager, target, room_manager, mob_manager, value)

        elif effect == 'evasion':
            # Implement temporary evasion increase
            character['stats']['Agility'] += value
            client_socket.sendall(f"You use '{skill.get('name')}', increasing your evasion by {value}% for {cooldown} seconds.\n".encode())
            logging.info(f"Character '{character['name']}' used skill '{skill.get('name')}' increasing Agility by {value}.")
            # Start a timer to revert the evasion boost
            threading.Thread(target=remove_evasion_boost, args=(character, value, cooldown, account_manager), kwargs={'username': character.get('username')}).start()

        elif effect == 'double_attack':
            if not target:
                client_socket.sendall(b"Usage: use skill <skill_name> <target>\n")
                logging.warning(f"Skill '{skill.get('name')}' requires a target but none was provided by '{character['name']}'.")
                return
            # Implement two consecutive attacks
            handle_double_attack(skill, character, client_socket, account_manager, target, room_manager, mob_manager)

        elif effect == 'area_damage':
            # Implement area damage to all mobs in the room
            handle_area_damage(skill, character, client_socket, account_manager, room_manager, mob_manager, value)

        elif effect == 'teleport_damage':
            if not target:
                client_socket.sendall(b"Usage: use skill <skill_name> <target>\n")
                logging.warning(f"Skill '{skill.get('name')}' requires a target but none was provided by '{character['name']}'.")
                return
            # Implement teleport behind target and deal critical damage
            handle_teleport_damage(skill, character, client_socket, account_manager, target, room_manager, mob_manager, value)

        else:
            client_socket.sendall(f"Skill '{skill.get('name')}' has an unknown effect.\n".encode())
            logging.warning(f"Skill '{skill.get('name')}' used by character '{character['name']}' has an unknown effect type '{effect}'.")

    except Exception as e:
        client_socket.sendall(b"An error occurred while executing the skill.\n")
        logging.error(f"Error executing skill '{skill.get('name')}' for character '{character['name']}': {e}")

    # Update character data after skill execution
    account_manager.update_character(character['username'], character)

def remove_evasion_boost(character, evasion_increase, duration, account_manager, username):
    """Removes the temporary evasion boost after the duration expires."""
    time.sleep(duration)
    character['stats']['Agility'] -= evasion_increase
    logging.info(f"Temporary evasion boost of {evasion_increase} removed from character '{character['name']}'.")
    account_manager.update_character(username, character)

def handle_skills(character: Dict, client_socket: socket.socket, skill_manager: Any) -> None:
    """Display character's available skills."""
    try:
        skills = character.get('skills', [])
        if not skills:
            client_socket.sendall(b"You have no skills.\n")
            return

        response = "Your skills:\n"
        for skill in skills:
            # Safely access skill attributes using get()
            skill_name = skill.get('name', 'Unknown Skill')
            skill_desc = skill.get('description', 'No description available.')
            skill_cost = skill.get('sp_cost', 0)
            skill_cd = skill.get('cooldown', 0)
            
            response += f"- {skill_name} (SP Cost: {skill_cost}, Cooldown: {skill_cd}s)\n"
            response += f"  Description: {skill_desc}\n"

        client_socket.sendall(response.encode())
    except Exception as e:
        logging.error(f"Error displaying skills: {str(e)}")
        client_socket.sendall(b"An error occurred while displaying skills.\n")

def handle_skill_use(username: str, character: Dict, args: List[str], client_socket: socket.socket, 
                    skill_manager: Any, account_manager: Any, room_manager: Any, 
                    mob_manager: Any, item_manager: Any) -> None:
    """Handle using a skill."""
    if not args:
        client_socket.sendall(b"Usage: skill <skill_name> [target]\n")
        return

    # Find where the skill name ends and target begins
    skill_words = []
    target_words = []
    found_skill = False

    # Build skill name one word at a time until we find a match
    for word in args:
        if not found_skill:
            skill_words.append(word)
            skill_name = ' '.join(skill_words)
            # Check if this combination is a valid skill
            character_skills = character.get('skills', [])
            for char_skill in character_skills:
                if char_skill['name'].lower() == skill_name.lower():
                    found_skill = True
                    skill = char_skill
                    break
        else:
            target_words.append(word)

    if not found_skill:
        client_socket.sendall(f"You don't know the skill '{' '.join(skill_words)}'.\n".encode())
        return

    target_name = ' '.join(target_words) if target_words else None

    # Execute the skill
    execute_skill(skill, character, client_socket, account_manager, target=target_name,
                 room_manager=room_manager, mob_manager=mob_manager, item_manager=item_manager)

def handle_cast(username, character, args, client_socket, spell_manager, account_manager):
    if not args:
        client_socket.sendall(b"Usage: cast <spell_name>\n")
        return

    spell_name = ' '.join(args).lower()
    spell = spell_manager.get_spell(character.get('class', 'wanderer'), spell_name)
    if spell:
        execute_spell(spell, character, client_socket, account_manager)
        account_manager.update_character(username, character)
    else:
        client_socket.sendall(f"You don't know the spell '{spell_name}'.\n".encode())

def execute_spell(spell, character, client_socket, account_manager):
    spell_name = spell.get('name', 'Unknown Spell')
    client_socket.sendall(f"You cast the spell '{spell_name}'.\n".encode())

    # Example: Restore SP
    if spell.get('effect') == 'restore_sp':
        restore_amount = spell.get('restore_amount', 10)
        character['stats']['SP'] = min(character['stats']['Max_SP'], character['stats']['SP'] + restore_amount)
        client_socket.sendall(f"The spell restores {restore_amount} SP.\n".encode())
        logging.info(f"Character '{character['name']}' cast '{spell_name}' and restored {restore_amount} SP.")
    else:
        client_socket.sendall(f"The spell '{spell_name}' has no effect.\n".encode())
        logging.warning(f"Spell '{spell_name}' has an undefined effect.")

    # Update character after spell effects
    account_manager.update_character(character['username'], character)

def handle_skill_damage(skill, character, client_socket, account_manager, target_name, room_manager, mob_manager, additional_damage):
    """
    Deals additional damage to a specified target.
    """
    current_room = room_manager.get_room(character.get('room'))
    if not current_room:
        client_socket.sendall(b"You are in an unknown place.\n")
        logging.error("Current room not found during skill damage.")
        return

    # Find the mob in the room by name
    mob_entry = next(
        (mob for mob in current_room.get('mobs', [])
         if target_name in mob_manager.get_mob_by_vnum(mob['vnum']).get('name', '').lower()),
        None
    )

    if mob_entry:
        mob = mob_manager.get_mob_by_vnum(mob_entry['vnum'])
        if mob:
            mob_stats = mob.get('stats', {}).copy()
            logging.debug(f"Skill Damage: Mob '{mob['name']}' stats: {mob_stats}")

            if 'HP' not in mob_stats or mob_stats['HP'] <= 0:
                client_socket.sendall(b"This creature is already dead.\n")
                logging.info(f"Attempted to use skill damage on an already dead mob '{mob['name']}'.")
                return

            # Calculate total damage
            base_damage = calculate_player_damage(character, mob_stats)
            total_damage = base_damage + additional_damage
            mob_stats['HP'] -= total_damage
            client_socket.sendall(f"You use '{skill.get('name')}' on {mob.get('name')}, dealing {total_damage} damage!\n".encode())
            logging.info(f"Character '{character['name']}' used skill '{skill.get('name')}' on mob '{mob['name']}', dealing {total_damage} damage. Mob HP left: {mob_stats['HP']}")

            # Update mob's HP
            mob['stats']['HP'] = mob_stats['HP']
            mob_manager.update_mob(mob['vnum'], mob)

            if mob['stats']['HP'] <= 0:
                # Handle mob defeat
                handle_attack(character['username'], character, target_name, client_socket, room_manager, mob_manager, account_manager, item_manager=None)  # Assuming item_manager is accessible
        else:
            client_socket.sendall(f"You don't see '{target_name}' here.\n".encode())
            logging.error(f"Mob with vnum '{mob_entry['vnum']}' not found in MobManager during skill damage.")
    else:
        client_socket.sendall(f"You don't see '{target_name}' here.\n".encode())
        logging.info(f"Mob '{target_name}' not found in room '{current_room.get('name', 'Unknown')}' during skill damage.")

def handle_double_attack(skill, character, client_socket, account_manager, target_name, room_manager, mob_manager):
    """
    Allows the character to perform two consecutive attacks on the target.
    """
    for attack_number in range(1, 3):
        client_socket.sendall(f"Executing attack {attack_number} with '{skill.get('name')}'.\n".encode())
        logging.debug(f"Executing attack {attack_number} with skill '{skill.get('name')}' for character '{character['name']}'.")
        handle_attack(character['username'], character, target_name, client_socket, room_manager, mob_manager, account_manager, item_manager=None)
        time.sleep(1)  # Short delay between attacks

def handle_area_damage(skill, character, client_socket, account_manager, room_manager, mob_manager, additional_damage):
    """
    Deals damage to all mobs in the current room.
    """
    current_room = room_manager.get_room(character.get('room'))
    if not current_room:
        client_socket.sendall(b"You are in an unknown place.\n")
        logging.error("Current room not found during area damage.")
        return

    mobs = current_room.get('mobs', [])
    if not mobs:
        client_socket.sendall(b"There are no creatures here to damage.\n")
        logging.info(f"Character '{character['name']}' used area damage skill '{skill.get('name')}' but no mobs are present.")
        return

    for mob_entry in mobs.copy():  # Use copy to avoid modification during iteration
        mob = mob_manager.get_mob_by_vnum(mob_entry['vnum'])
        if mob and mob['stats'].get('HP', 0) > 0:
            base_damage = calculate_player_damage(character, mob['stats'])
            total_damage = base_damage + additional_damage
            mob['stats']['HP'] -= total_damage
            client_socket.sendall(f"You use '{skill.get('name')}' on {mob.get('name')}, dealing {total_damage} damage!\n".encode())
            logging.info(f"Character '{character['name']}' used area damage skill '{skill.get('name')}' on mob '{mob['name']}', dealing {total_damage} damage. Mob HP left: {mob['stats']['HP']}")

            if mob['stats']['HP'] <= 0:
                # Handle mob defeat
                handle_attack(character['username'], character, mob.get('name'), client_socket, room_manager, mob_manager, account_manager, item_manager=None)
        else:
            logging.warning(f"Mob with vnum '{mob_entry['vnum']}' not found or already dead during area damage.")

def handle_teleport_damage(skill, character, client_socket, account_manager, target_name, room_manager, mob_manager, critical_damage):
    """
    Teleports the character behind the target and deals critical damage.
    """
    current_room = room_manager.get_room(character.get('room'))
    if not current_room:
        client_socket.sendall(b"You are in an unknown place.\n")
        logging.error("Current room not found during teleport damage.")
        return

    # Find the mob in the room by name
    mob_entry = next(
        (mob for mob in current_room.get('mobs', [])
         if target_name in mob_manager.get_mob_by_vnum(mob['vnum']).get('name', '').lower()),
        None
    )

    if mob_entry:
        mob = mob_manager.get_mob_by_vnum(mob_entry['vnum'])
        if mob:
            # Simulate teleportation
            client_socket.sendall(f"You teleport behind {mob.get('name')}!\n".encode())
            logging.info(f"Character '{character['name']}' teleported behind mob '{mob['name']}'.")

            # Deal critical damage
            mob_stats = mob.get('stats', {}).copy()
            mob_stats['HP'] -= critical_damage
            client_socket.sendall(f"You deal {critical_damage} critical damage to {mob.get('name')}!\n".encode())
            logging.info(f"Character '{character['name']}' dealt {critical_damage} critical damage to mob '{mob['name']}'. Mob HP left: {mob_stats['HP']}")

            # Update mob's HP
            mob['stats']['HP'] = mob_stats['HP']
            mob_manager.update_mob(mob['vnum'], mob)

            if mob['stats']['HP'] <= 0:
                # Handle mob defeat
                handle_attack(character['username'], character, mob.get('name'), client_socket, room_manager, mob_manager, account_manager, item_manager=None)
        else:
            client_socket.sendall(f"You don't see '{target_name}' here.\n".encode())
            logging.error(f"Mob with vnum '{mob_entry['vnum']}' not found in MobManager during teleport damage.")
    else:
        client_socket.sendall(f"You don't see '{target_name}' here.\n".encode())
        logging.info(f"Mob '{target_name}' not found in room '{current_room.get('name', 'Unknown')}' during teleport damage.")

def handle_read(character, args, client_socket, room_manager, item_manager):
    if not args:
        client_socket.sendall(b"Usage: read <item>\n")
        return

    target_name = ' '.join(args).lower()
    current_room = room_manager.get_room(character['room'])

    if not current_room:
        client_socket.sendall(b"You are in an unknown place.\n")
        return

    # Check for readable items in the room
    for item_entry in current_room.get('items', []):
        item = item_manager.get_item_by_vnum(item_entry['vnum'], item_entry['type'])
        if item and target_name in item.get('name', '').lower() and item.get('readable', False):
            client_socket.sendall(f"{item.get('read_text', 'You cannot read this.')}\n".encode())
            return

    client_socket.sendall(f"You don't see anything to read called '{target_name}'.\n".encode())

def find_item_in_inventory(target_name, inventory):
    # Check for numbered item, e.g., '2.sword'
    match = re.match(r'^(\d+)\.(.+)', target_name)
    if match:
        index = int(match.group(1))
        name = match.group(2).strip()
    else:
        index = 1
        name = target_name.strip()

    # Find all matching items
    matching_items = [item for item in inventory if name in item.get('name', '').lower()]
    if len(matching_items) >= index:
        return matching_items[index - 1]
    else:
        return None

def find_item_in_room(target_name, room_items, item_manager):
    """Find an item in the room, including containers."""
    # Check for numbered item, e.g., '2.sword'
    match = re.match(r'^(\d+)\.(.+)', target_name)
    if match:
        index = int(match.group(1))
        name = match.group(2).strip()
    else:
        index = 1
        name = target_name.strip()

    # Find all matching items
    matching_items = []
    for item_entry in room_items:
        # Direct match for items that have their own name (like containers)
        if name in item_entry.get('name', '').lower():
            matching_items.append((item_entry, item_entry))
            continue
            
        # Look up base item data for other items
        try:
            room_item = item_manager.get_item_by_vnum(item_entry['vnum'], item_entry.get('type'))
            if room_item and name in room_item.get('name', '').lower():
                matching_items.append((item_entry, room_item))
        except Exception as e:
            logging.error(f"Error retrieving item vnum {item_entry.get('vnum')} of type {item_entry.get('type')}: {e}")
            continue

    if len(matching_items) >= index:
        return matching_items[index - 1]  # Returns tuple (item_entry, room_item)
    else:
        return None, None

def find_mob_in_room(target_name, room_mobs, mob_manager):
    # Check for numbered mob, e.g., '2.goblin'
    match = re.match(r'^(\d+)\.(.+)', target_name)
    if match:
        index = int(match.group(1))
        name = match.group(2).strip()
    else:
        index = 1
        name = target_name.strip()

    # Find all matching mobs
    matching_mobs = []
    for mob_entry in room_mobs:
        mob = mob_manager.get_mob_by_vnum(mob_entry['vnum'])
        if mob and name in mob.get('name', '').lower():
            matching_mobs.append(mob_entry)

    if len(matching_mobs) >= index:
        return matching_mobs[index - 1]
    else:
        return None

def handle_help(args, client_socket, character, room_manager, item_manager, mob_manager, account_manager):
    help_topics = {
        # Player Stats
        "strength": "Strength Stat: Determines your physical power. Higher Strength increases the damage you deal with melee weapons.",
        "tenacity": "Tenacity Stat: Represents your toughness and resilience. Higher Tenacity reduces the damage you take from enemy attacks.",
        "agility": "Agility Stat: Affects your speed and reflexes. Higher Agility increases your chance to dodge enemy attacks.",
        "intelligence": "Intelligence Stat: Measures your mental acuity. Higher Intelligence enhances your effectiveness with spells and magical abilities.",
        "revel": "Revel Stat: Reflects your connection to the mystical energies. Higher Revel boosts the potency of certain special abilities.",
        "defense": "Defense Stat: Comes from your equipped armor. Higher Defense directly reduces the physical damage you take from enemies.",
        
        # Chat Commands
        "say": "Say Command: Use '/say <message>' to speak to everyone in your current room.",
        "whisper": "Whisper Command: Use '/whisper <name> <message>' to send a private message to someone in the same room.",
        "ooc": "OOC Command: Use '/ooc <message>' to speak out of character to everyone across the entire MUD.",
        "shout": "Shout Command: Use '/shout <message>' to shout across the entire MUD.",
        "tell": "Tell Command: Use '/tell <player name> <message>' to send a private message to a player anywhere in the MUD.",
        "reply": "Reply Command: Use '/reply' or '/r <message>' to reply to the last player who sent you a private message.",
        "broadcast": "Broadcast Command: Use '/broadcast <message>' (admin only) to send an announcement to the entire MUD.",

        # Container Commands
        "put": """Put Command: Place items into containers.
Usage: put <item> in <container>
Example: put potion in chest""",
        "lock": "Lock Command: Lock a container if you have the proper key. Usage: lock <container>",
        "unlock": "Unlock Command: Unlock a container if you have the proper key. Usage: unlock <container>",

        # Regular Commands
"flee": """Flee Command: Attempt to escape from combat.
Usage: flee
- Success chance is based on your Agility
- Higher level enemies are easier to flee from
- Fleeing will move you to a random connected room
- You cannot flee if there are no exits available""",
        "drop": "Drop Command: Use 'drop <item name>' to remove an item from your inventory and place it in the current room.",
        "get": """Get Command: Allows you to pick up items from the room or from containers.
Usage:
- 'get <item>': Pick up a specific item from the room.
- 'get all': Pick up all items from the room.
- 'get <item> from <container>': Retrieve a specific item from a container.
- 'get all from <container>': Retrieve all items from a container.""",
        "wear": "Wear Command: Use 'wear <armor name>' to equip armor items and increase your Defense.",
        "wield": "Wield Command: Use 'wield <weapon name>' to equip weapon items and increase your attack capabilities.",
        "attack": "Attack Command: Use 'attack <mob name>' to initiate combat with a mob in the room.",
        "skills": "Skills Command: Use 'skills' to view the skills you have learned and their descriptions.",
        "summon": "Summon Command: Use '@<asum/wsum/csum/msum/bagsum> <vnum> [inv|here]' to summon items into your inventory or the room. Admin only.",
        "eat": "Eat Command: Use 'eat <food item>' to consume food and restore some HP.",
        "drink": "Drink Command: Use 'drink <drink item>' to consume a drink or potion, which may restore SP or have other effects.",
        "look": "Look Command: Use 'look' or 'l' to see your surroundings, including room description and visible objects.",
        "inventory": "Inventory Command: Use 'inventory', 'inv', or 'i' to view the items you are currently carrying.",
        "examine": "Examine Command: Use 'examine <item/mob>' to get a detailed description of an item or mob.",
        "move": "Movement Commands: Use directions like 'north', 'south', 'east', 'west', or their abbreviations 'n', 's', 'e', 'w' to move between rooms.",
        "help": "Help Command: Use 'help' to see a list of available commands or 'help <topic>' for detailed information on a specific topic.",
        "destroy": "Destroy Command: Use 'destroy <item/mob> [here|inv]' to permanently remove an item or mob. Admin only."
    }

    if not args:
        general_help = "Available commands and topics:\n" + "\n".join([f"- {cmd}" for cmd in sorted(help_topics.keys())]) + "\nUse 'help <command/topic>' for more details."
        client_socket.sendall(general_help.encode())
        return

    topic = args[0].lower()
    if topic in help_topics:
        client_socket.sendall(f"{help_topics[topic]}\n".encode())
    else:
        client_socket.sendall(b"No help available for that topic.\n")

def grant_skills_on_login(character, username, skill_manager, account_manager, client_socket):
    """
    Grants skills to the character based on their class and level.
    """
    char_class = character.get('class', 'wanderer')
    level = character.get('level', 1)
    
    available_skills = skill_manager.get_available_skills(char_class, level)
    learned_skills = character.get('skills', [])
    
    new_skills = []
    
    for skill in available_skills:
        skill_name = skill.get('name').lower()
        if skill_name not in [s.lower() for s in learned_skills]:
            learned_skills.append(skill.get('name'))
            new_skills.append(skill.get('name'))
            logging.info(f"Granted skill '{skill.get('name')}' to character '{character['name']}' (Level {level}).")
    
    if new_skills:
        character['skills'] = learned_skills
        account_manager.update_character(username, character)
        message = f"You have learned new skills: {', '.join(new_skills)}.\n"
        client_socket.sendall(message.encode())

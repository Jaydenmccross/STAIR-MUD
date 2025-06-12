
from typing import Dict, Any, Optional, List, Tuple
import logging
import random
import time
import copy
import threading


# Effect and Target type definitions
class EffectType:
    DOT = "dot"
    HOT = "hot"
    BUFF = "buff"
    DEBUFF = "debuff"

class TargetType:
    SELF = "self"
    SINGLE = "single"
    AREA = "area"

class EffectHandler:
    def __init__(self):
        self.active_effects = {}
        self.lock = threading.RLock()
    
    def apply_effect(self, target, effect_type, value, duration):
        with self.lock:
            target_id = target.get('instance_id', target.get('name'))
            if target_id not in self.active_effects:
                self.active_effects[target_id] = []
            
            effect = {
                'type': effect_type,
                'value': value,
                'end_time': time.time() + duration
            }
            self.active_effects[target_id].append(effect)
            logging.debug(f"Applied {effect_type} effect to {target_id}")
    
    def remove_effect(self, target, effect_type):
        with self.lock:
            target_id = target.get('instance_id', target.get('name'))
            if target_id in self.active_effects:
                self.active_effects[target_id] = [
                    effect for effect in self.active_effects[target_id]
                    if effect['type'] != effect_type
                ]
                logging.debug(f"Removed {effect_type} effects from {target_id}")
    
    def process_effects(self, target):
        with self.lock:
            target_id = target.get('instance_id', target.get('name'))
            if target_id not in self.active_effects:
                return
            
            current_time = time.time()
            active = []
            
            for effect in self.active_effects[target_id]:
                if current_time < effect['end_time']:
                    active.append(effect)
                else:
                    logging.debug(f"Effect expired for {target_id}")
                    
            self.active_effects[target_id] = active

class CombatManager:
    def __init__(self, effect_handler, mob_manager):
        self.effect_handler = effect_handler
        self.mob_manager = mob_manager
        self.active_combats = {}
        self.combat_lock = threading.RLock()
        
    def handle_flee(self, character, client_socket, room_manager, mob_manager, account_manager):
        """Handle a character attempting to flee from combat."""
        with self.combat_lock:
            try:
                if character['name'] not in self.active_combats:
                    client_socket.sendall(b"You're not in combat!\n")
                    return False
                
                combat_session = self.active_combats[character['name']]
                current_room = room_manager.get_room(character['room'])
                
                if not current_room or not current_room.get('exits'):
                    client_socket.sendall(b"There's nowhere to flee to!\n")
                    return False
                
                # Calculate flee chance based on agility
                agility = character['stats'].get('Agility', 0)
                base_chance = 40  # 40% base chance
                flee_chance = min(80, base_chance + (agility * 2))  # Cap at 80%
                
                if random.uniform(0, 100) <= flee_chance:
                    # Choose random exit
                    available_exits = list(current_room['exits'].items())
                    direction, new_room_vnum = random.choice(available_exits)
                    
                    # Move character to new room
                    old_room_vnum = character['room']
                    room_manager.remove_player_from_room(old_room_vnum, character['username'])
                    room_manager.add_player_to_room(new_room_vnum, character['username'], character['name'])
                    
                    # Update character location and combat status
                    character['room'] = new_room_vnum
                    character['in_combat'] = False
                    account_manager.update_character(character['username'], character)
                    
                    # End combat session completely
                    self.end_combat(combat_session)
                    
                    # Send messages
                    client_socket.sendall(f"You successfully flee to the {direction}!\n".encode())
                    client_socket.sendall(self.format_player_stats(character).encode())
                    logging.info(f"Character {character['name']} successfully fled to room {new_room_vnum}")
                    return True
                else:
                    client_socket.sendall(b"You fail to flee!\n")
                    client_socket.sendall(self.format_player_stats(character).encode())
                    logging.debug(f"Character {character['name']} failed to flee")
                    return False
                    
            except Exception as e:
                logging.error(f"Error in handle_flee for character {character['name']}: {e}")
                client_socket.sendall(b"An error occurred while trying to flee.\n")
                return False

    def initiate_combat(self, character: Dict, target_name: str, client_socket: Any,
                       room_manager: Any, mob_manager: Any, account_manager: Any,
                       item_manager: Any) -> bool:
        """Initialize combat with proper instance handling."""
        with self.combat_lock:
            try:
                if character['name'] in self.active_combats:
                    client_socket.sendall(b"You're already in combat!\n")
                    return False

                current_room = room_manager.get_room(character.get('room'))
                if not current_room:
                    client_socket.sendall(b"You are in an unknown place.\n")
                    return False

                # Find target mob
                target_mob_entry = None
                for mob_entry in current_room.get('mobs', []):
                    # Skip template entries
                    if mob_entry.get('is_template', False):
                        continue
                        
                    mob = mob_manager.get_mob_by_vnum(mob_entry['vnum'])
                    if mob and target_name.lower() in mob['name'].lower():
                        # Use the instance ID from the room's mob entry
                        mob['instance_id'] = mob_entry.get('instance_id')
                        target_mob_entry = mob_entry
                        target = copy.deepcopy(mob)
                        break

                if not target_mob_entry or not target:
                    client_socket.sendall(f"You don't see '{target_name}' here.\n".encode())
                    return False

                if target['stats']['HP'] <= 0:
                    client_socket.sendall(b"That creature is already dead.\n")
                    return False

                # Set combat flags
                character['in_combat'] = True
                
                # Create combat session with instance tracking
                combat_session = {
                    'attacker': character,
                    'defender': target,
                    'defender_entry': target_mob_entry,  # Keep the original entry reference
                    'start_time': time.time(),
                    'last_attack': 0,
                    'round': 0,
                    'status_effects': []
                }
                
                self.active_combats[character['name']] = combat_session
                logging.info(f"Combat initiated between {character['name']} and {target['name']} ({target.get('instance_id')})")
                
                # Start combat round
                self.process_combat_round(
                    combat_session=combat_session,
                    client_socket=client_socket,
                    room_manager=room_manager,
                    mob_manager=mob_manager,
                    account_manager=account_manager,
                    item_manager=item_manager
                )
                return True

            except Exception as e:
                logging.error(f"Error initiating combat for character {character['name']}: {e}")
                client_socket.sendall(b"An error occurred while initiating combat.\n")
                return False

    def process_combat_round(self, combat_session: Dict, client_socket: Any,
                           room_manager: Any, mob_manager: Any, 
                           account_manager: Any, item_manager: Any):
        """Process a single round of combat"""
        try:
            attacker = combat_session['attacker']
            defender = combat_session['defender']
            combat_session['round'] += 1

            # Process status effects
            self.process_status_effects(combat_session, client_socket)

            # Check if defender should flee
            if self.should_mob_flee(defender):
                if self.handle_mob_flee(defender, combat_session, client_socket, 
                                      room_manager, mob_manager):
                    return

            # Process attacks
            if self.can_attack(attacker, defender, client_socket):  # Add client_socket here
                damage = self.calculate_damage(attacker, defender, client_socket)
                self.apply_damage(defender, damage, client_socket, attacker=attacker)
                
                if defender['stats']['HP'] <= 0:
                    self.handle_combat_victory(
                        combat_session=combat_session,
                        client_socket=client_socket,
                        room_manager=room_manager,
                        mob_manager=mob_manager,
                        account_manager=account_manager,
                        item_manager=item_manager
                    )
                    return

                # Mob counterattack
                if defender['stats']['HP'] > 0 and self.can_attack(defender, attacker, client_socket):  # Add client_socket here
                    mob_damage = self.calculate_mob_damage(defender, attacker)
                    self.apply_damage(attacker, mob_damage, client_socket, attacker=defender, is_mob=True)
                    
                    if attacker['stats']['HP'] <= 0:
                        self.handle_player_death(
                            combat_session=combat_session,
                            client_socket=client_socket,
                            account_manager=account_manager
                        )
                        return

            # Schedule next round if combat continues
            if (combat_session['attacker']['stats']['HP'] > 0 and 
                combat_session['defender']['stats']['HP'] > 0):
                threading.Timer(
                    2.0,  # Combat round delay
                    self.process_combat_round,
                    args=[combat_session, client_socket, room_manager, 
                          mob_manager, account_manager, item_manager]
                ).start()

        except Exception as e:
            logging.error(f"Error in combat round: {e}")
            self.handle_combat_error(combat_session, client_socket)

    def should_mob_flee(self, mob: Dict) -> bool:
        """Determine if a mob should attempt to flee based on its settings."""
        try:
            if mob.get('is_aggressive', False):
                return False
                
            current_hp = mob['stats']['HP']
            max_hp = mob['stats']['Max_HP']
            flee_threshold = mob.get('flee_threshold', 20)  # Default 20% HP
            
            return (current_hp / max_hp * 100) <= flee_threshold
        except Exception as e:
            logging.error(f"Error checking if mob should flee: {e}")
            return False

    def handle_mob_flee(self, mob: Dict, combat_session: Dict, 
                       client_socket: Any, room_manager: Any, mob_manager: Any) -> bool:
        """Handle mob fleeing from combat."""
        try:
            current_room = room_manager.get_room(mob.get('room'))
            if not current_room or not current_room.get('exits'):
                return False

            # Choose random exit
            direction, new_room_vnum = random.choice(list(current_room['exits'].items()))
            
            # Move mob to new room
            mob_instance_id = mob.get('instance_id')
            if mob_manager.move_mob(mob_instance_id, current_room['vnum'], new_room_vnum):
                # End combat session
                combat_session['attacker']['in_combat'] = False
                self.end_combat(combat_session)
                
                # Send messages
                client_socket.sendall(f"{mob['name']} flees to the {direction}!\n".encode())
                client_socket.sendall(self.format_player_stats(combat_session['attacker']).encode())
                logging.info(f"Mob {mob['name']} ({mob_instance_id}) fled to room {new_room_vnum}")
                return True
            
            return False

        except Exception as e:
            logging.error(f"Error handling mob flee: {e}")
            return False

    def handle_combat_error(self, combat_session: Dict, client_socket: Any):
        """Handle errors during combat gracefully."""
        try:
            # End combat session
            self.end_combat(combat_session)
            
            # Notify player
            client_socket.sendall(b"An error occurred during combat. Combat has been ended.\n")
            
        except Exception as e:
            logging.error(f"Error handling combat error: {e}")

    def handle_combat_victory(self, combat_session: Dict, client_socket: Any,
                         room_manager: Any, mob_manager: Any, 
                         account_manager: Any, item_manager: Any):
        """Handle mob death and combat cleanup with proper instance tracking."""
        try:
            character = combat_session['attacker']
            mob = combat_session['defender']
            instance_id = mob.get('instance_id')
            room_vnum = character.get('room')

            # Add these debug lines
            logging.debug(f"Combat victory - mob_manager type: {type(self.mob_manager)}")
            logging.debug(f"Combat victory - mob_manager methods: {dir(self.mob_manager)}")
            logging.debug(f"Combat victory - instance_id: {instance_id}")
            logging.debug(f"Combat victory - room_vnum: {room_vnum}")

            if not instance_id:
                logging.error("No instance ID found for mob")
                return

            if not room_vnum:
                logging.error("No room vnum found for character")
                return

            # Handle mob death through mob manager
            if mob_manager.handle_mob_death(instance_id, room_vnum, room_manager, item_manager):
                # Grant experience
                exp_gain = mob.get('exp', 0)
                character['experience'] = character.get('experience', 0) + exp_gain

                # Send victory message
                client_socket.sendall(
                    f"You have defeated {mob['name']} and gained {exp_gain} experience!\n".encode()
                )

                # Check for level up
                self.check_for_level_up(
                    character=character,
                    client_socket=client_socket,
                    account_manager=account_manager
                )
            else:
                logging.error(f"Failed to handle death for mob instance {instance_id}")

        except Exception as e:
            logging.error(f"Error in handle_combat_victory: {e}")
        finally:
            # Always end combat, even if there was an error
            self.end_combat(combat_session)

    def end_combat(self, combat_session):
        """End the combat session and clean up."""
        try:
            # Clear combat flags
            attacker = combat_session['attacker']
            attacker['in_combat'] = False
            
            # Remove from active combats
            if attacker['name'] in self.active_combats:
                del self.active_combats[attacker['name']]
            
            # Clear any combat-specific effects or states
            combat_session['status_effects'].clear()
            
            logging.info(f"Combat ended for {attacker['name']}")

        except Exception as e:
            logging.error(f"Error ending combat: {e}")

    def generate_loot(self, mob, corpse):
        """Generate and validate loot for a defeated mob."""
        try:
            # Process loot pool
            loot_pool = mob.get('loot_pool', [])
            for loot_entry in loot_pool:
                try:
                    if not all(key in loot_entry for key in ['type', 'vnum', 'drop_rate']):
                        logging.warning(f"Invalid loot entry found: {loot_entry}")
                        continue

                    drop_rate = float(loot_entry.get('drop_rate', 0))
                    if random.uniform(0, 100) <= drop_rate:
                        loot_item = {
                            'vnum': loot_entry['vnum'],
                            'type': loot_entry['type'],
                            'quantity': int(loot_entry.get('quantity', 1))
                        }
                        corpse['contents'].append(loot_item)
                        logging.debug(f"Added loot item to corpse: {loot_item}")

                except (ValueError, TypeError) as e:
                    logging.error(f"Error processing loot entry {loot_entry}: {e}")
                    continue

            # Handle gold drops
            try:
                gold_base = int(mob.get('gold', 0))
                if gold_base > 0:
                    gold_amount = random.randint(gold_base, int(gold_base * 1.5))
                    corpse['contents'].append({
                        'vnum': 'gold',
                        'type': 'currency',
                        'quantity': gold_amount
                    })
                    logging.debug(f"Added {gold_amount} gold to corpse")

            except (ValueError, TypeError) as e:
                logging.error(f"Error processing gold drop: {e}")

        except Exception as e:
            logging.error(f"Error generating loot for mob {mob.get('name')}: {e}")

    def apply_damage(self, target: Dict, damage: int, client_socket: Any, attacker: Dict = None, is_mob: bool = False):
        """Apply damage with improved combat feedback."""
        try:
            old_hp = target['stats']['HP']
            max_hp = target['stats'].get('Max_HP', old_hp)
            target['stats']['HP'] = max(0, old_hp - damage)
            
            # Calculate damage reduction percentage for informative message
            damage_reduction = target['stats'].get('Defense', 0)
            if damage_reduction > 0:
                reduced_amount = min(damage, damage_reduction)
                damage_message = f" ({reduced_amount} blocked)"
            else:
                damage_message = ""
            
            # Update combat message and stats display
            if is_mob and attacker:
                # Mob attacking player
                message = f"{attacker.get('name', 'Unknown')} hits you for {damage} damage{damage_message}!\n"
                # Only show player stats, not mob HP
                message += self.format_player_stats(target)
            else:
                # Player attacking mob
                message = f"You hit {target.get('name', 'Unknown')} for {damage} damage{damage_message}!\n"
                if attacker:
                    message += self.format_player_stats(attacker)

            client_socket.sendall(message.encode())
            
            logging.debug(
                f"{'Mob' if is_mob else 'Player'} dealt {damage} damage to {target.get('name')}. "
                f"HP: {old_hp}->{target['stats']['HP']} (Reduction: {damage_reduction})"
            )

        except Exception as e:
            logging.error(f"Error applying damage: {e}")

    def format_player_stats(self, character: Dict) -> str:
        """Format player stats display with colors and percentages."""
        try:
            # Calculate percentages
            hp_percent = (character['stats']['HP'] / character['stats']['Max_HP']) * 100
            sp_percent = (character['stats']['SP'] / character['stats']['Max_SP']) * 100
            ap_percent = (character['stats']['AP'] / character['stats']['Max_AP']) * 100 if character['stats']['Max_AP'] > 0 else 0

            # Color coding based on percentages
            def get_color(percent):
                if percent > 66:
                    return "\033[32m"  # Green
                elif percent > 33:
                    return "\033[33m"  # Yellow
                else:
                    return "\033[31m"  # Red

            RESET = "\033[0m"
            
            hp_color = get_color(hp_percent)
            sp_color = get_color(sp_percent)
            ap_color = get_color(ap_percent)

            return (
                f"{hp_color}HP: {character['stats']['HP']}/{character['stats']['Max_HP']}{RESET} | "
                f"{sp_color}SP: {character['stats']['SP']}/{character['stats']['Max_SP']}{RESET} | "
                f"{ap_color}AP: {character['stats']['AP']}/{character['stats']['Max_AP']}{RESET}\n"
            )

        except Exception as e:
            logging.error(f"Error formatting player stats: {e}")
            return "Error displaying stats\n"

    def process_status_effects(self, combat_session: Dict, client_socket: Any):
        """Enhanced status effect processing with proper cleanup."""
        try:
            current_time = time.time()
            
            # Process each combatant's effects
            for participant in ['attacker', 'defender']:
                entity = combat_session[participant]
                entity_id = entity.get('instance_id', entity.get('name'))
                effects_to_remove = []
                
                for effect in combat_session['status_effects'][:]:
                    if effect.get('target_id') != entity_id:
                        continue
                        
                    if current_time >= effect['end_time']:
                        effects_to_remove.append(effect)
                        continue
                        
                    self.apply_status_effect(effect, entity, client_socket)
                
                # Clean up expired effects
                for effect in effects_to_remove:
                    self.remove_status_effect(combat_session, effect, client_socket)

        except Exception as e:
            logging.error(f"Error processing status effects: {e}")

    def apply_status_effect(self, effect: Dict, target: Dict, client_socket: Any):
        """Apply a single status effect tick."""
        try:
            effect_type = effect.get('type')
            value = effect.get('value', 0)
            
            if effect_type == 'dot':  # Damage over time
                if target['stats']['HP'] > 0:
                    old_hp = target['stats']['HP']
                    target['stats']['HP'] = max(0, old_hp - value)
                    client_socket.sendall(
                        f"{effect.get('name', 'Effect')} deals {value} damage to {target['name']}.\n"
                        .encode()
                    )
                    
            elif effect_type == 'hot':  # Healing over time
                max_hp = target['stats'].get('Max_HP', target['stats']['HP'])
                if target['stats']['HP'] < max_hp:
                    old_hp = target['stats']['HP']
                    target['stats']['HP'] = min(max_hp, old_hp + value)
                    client_socket.sendall(
                        f"{effect.get('name', 'Effect')} heals {target['name']} for {value} HP.\n"
                        .encode()
                    )
                    
            elif effect_type == 'buff':
                # Buffs are applied when the effect starts
                pass
                
            elif effect_type == 'debuff':
                # Debuffs are applied when the effect starts
                pass
                
            logging.debug(
                f"Applied {effect_type} effect to {target['name']}: {value}"
            )

        except Exception as e:
            logging.error(f"Error applying status effect: {e}")

    def add_combat_effect(self, combat_session: Dict, effect_type: str, target: Dict, 
                         value: int, duration: int, name: str = None, 
                         client_socket: Any = None):
        """Add a new combat effect with proper validation."""
        try:
            target_id = target.get('instance_id', target.get('name'))
            
            # Create effect
            effect = {
                'type': effect_type,
                'target_id': target_id,
                'value': value,
                'start_time': time.time(),
                'end_time': time.time() + duration,
                'name': name or effect_type.title()
            }
            
            # Apply initial effect
            if effect_type == 'buff':
                if 'stat' in effect and 'value' in effect:
                    target['stats'][effect['stat']] += effect['value']
                    if client_socket:
                        client_socket.sendall(
                            f"{target['name']} gains {effect['value']} {effect['stat']}.\n"
                            .encode()
                        )
                        
            elif effect_type == 'debuff':
                if 'stat' in effect and 'value' in effect:
                    target['stats'][effect['stat']] -= effect['value']
                    if client_socket:
                        client_socket.sendall(
                            f"{target['name']} loses {effect['value']} {effect['stat']}.\n"
                            .encode()
                        )
            
            # Add to combat session
            combat_session['status_effects'].append(effect)
            
            logging.debug(
                f"Added {effect_type} effect to {target['name']}: "
                f"value={value}, duration={duration}"
            )
            
            return True

        except Exception as e:
            logging.error(f"Error adding combat effect: {e}")
            return False

    def remove_status_effect(self, combat_session: Dict, effect: Dict, 
                           client_socket: Any = None):
        """Remove a status effect and revert its changes."""
        try:
            # Find target
            target = None
            for participant in ['attacker', 'defender']:
                entity = combat_session[participant]
                if entity.get('instance_id', entity.get('name')) == effect.get('target_id'):
                    target = entity
                    break
                    
            if not target:
                logging.warning(f"Target not found for effect removal: {effect}")
                return
                
            # Revert effect changes
            effect_type = effect.get('type')
            if effect_type == 'buff':
                if 'stat' in effect and 'value' in effect:
                    target['stats'][effect['stat']] -= effect['value']
                    if client_socket:
                        client_socket.sendall(
                            f"{effect['name']} fades from {target['name']}.\n"
                            .encode()
                        )
                        
            elif effect_type == 'debuff':
                if 'stat' in effect and 'value' in effect:
                    target['stats'][effect['stat']] += effect['value']
                    if client_socket:
                        client_socket.sendall(
                            f"{effect['name']} fades from {target['name']}.\n"
                            .encode()
                        )
            
            # Remove from combat session
            combat_session['status_effects'].remove(effect)
            
            logging.debug(
                f"Removed {effect_type} effect from {target['name']}: {effect.get('name')}"
            )

        except Exception as e:
            logging.error(f"Error removing status effect: {e}")

    def calculate_combat_modifiers(self, attacker: Dict, defender: Dict) -> dict:
        """Calculate combat modifiers including critical hits and dodges."""
        try:
            modifiers = {
                'is_critical': False,
                'is_dodge': False,
                'damage_multiplier': 1.0,
                'hit_chance': 100.0
            }
            
            # Calculate dodge chance
            defender_agility = defender['stats'].get('Agility', 0)
            dodge_chance = CombatUtility.calculate_dodge_chance(defender_agility)
            
            # Check for dodge
            if random.uniform(0, 100) <= dodge_chance:
                modifiers['is_dodge'] = True
                return modifiers
                
            # Calculate critical hit chance
            attacker_agility = attacker['stats'].get('Agility', 0)
            attacker_strength = attacker['stats'].get('Strength', 0)
            crit_chance = CombatUtility.calculate_crit_chance(attacker_agility, 
                                                            attacker_strength)
                                                            
            # Check for critical hit
            if random.uniform(0, 100) <= crit_chance:
                modifiers['is_critical'] = True
                modifiers['damage_multiplier'] = CombatUtility.calculate_crit_multiplier(
                    attacker_strength
                )
                
            # Calculate hit chance
            attacker_skill = attacker['stats'].get('Strength', 0)  # Use strength for now
            defender_evasion = defender['stats'].get('Evasiveness', 0)
            modifiers['hit_chance'] = CombatUtility.calculate_hit_chance(
                attacker_skill, defender_evasion
            )
            
            return modifiers

        except Exception as e:
            logging.error(f"Error calculating combat modifiers: {e}")
            return {
                'is_critical': False,
                'is_dodge': False,
                'damage_multiplier': 1.0,
                'hit_chance': 100.0
            }

    def apply_combat_message(self, message: str, client_socket: Any, 
                           is_critical: bool = False, 
                           is_dodge: bool = False):
        """Apply formatting to combat messages."""
        try:
            if is_critical:
                message = f"CRITICAL! {message}"
            elif is_dodge:
                message = f"DODGE! {message}"
                
            client_socket.sendall(f"{message}\n".encode())

        except Exception as e:
            logging.error(f"Error sending combat message: {e}")
            try:
                client_socket.sendall(b"Combat continues...\n")
            except:
                pass

    def can_attack(self, attacker: Dict, defender: Dict, client_socket: Any = None) -> bool:
        """Determine if an attacker can successfully attack a defender."""
        try:
            modifiers = self.calculate_combat_modifiers(attacker, defender)
            if modifiers['is_dodge'] and client_socket:
                self.apply_combat_message(f"{defender['name']} dodges your attack!", client_socket)
                return False
            
            if random.uniform(0, 100) > modifiers['hit_chance'] and client_socket:
                self.apply_combat_message(f"You miss {defender['name']}!", client_socket)
                return False
            
            return True

        except Exception as e:
            logging.error(f"Error determining if attacker can attack: {e}")
            return False

    def end_combat(self, combat_session: Dict):
        """End the combat session and clean up."""
        try:
            # Clear combat flags
            attacker = combat_session['attacker']
            attacker['in_combat'] = False
            
            # Remove from active combats
            if attacker['name'] in self.active_combats:
                del self.active_combats[attacker['name']]
            
            # Clear any combat-specific effects or states
            combat_session['status_effects'].clear()
            
            logging.info(f"Combat ended for {attacker['name']}")

        except Exception as e:
            logging.error(f"Error ending combat: {e}")

    def calculate_damage(self, attacker: Dict, defender: Dict, client_socket: Any = None) -> int:
        """Calculate the damage dealt by the attacker to the defender."""
        try:
            # Get base stats
            strength = attacker['stats'].get('Strength', 0)
            
            # Get weapon damage
            weapon = attacker.get('equipment', {}).get('mainhand')
            min_damage = weapon.get('min_damage', 1) if weapon else 1
            max_damage = weapon.get('max_damage', 3) if weapon else 2
            
            # Calculate base weapon damage
            base_damage = random.randint(min_damage, max_damage)
            
            # Add strength bonus (every 2 points of strength adds 1 damage)
            strength_bonus = strength // 2
            
            # Get combat modifiers
            modifiers = self.calculate_combat_modifiers(attacker, defender)
            
            # Calculate total damage
            total_damage = (base_damage + strength_bonus) * modifiers['damage_multiplier']
            
            # Apply defender's defense and tenacity
            defense = defender['stats'].get('Defense', 0)
            tenacity = defender['stats'].get('Tenacity', 0)
            damage_reduction = defense + (tenacity // 2)
            
            # Calculate final damage (minimum 1)
            final_damage = max(1, int(total_damage - damage_reduction))
            
            # Handle critical hit message if applicable
            if modifiers['is_critical'] and client_socket:
                self.apply_combat_message(
                    f"Critical hit! ({final_damage} damage)", 
                    client_socket, 
                    is_critical=True
                )
                
            logging.debug(
                f"Damage calculation: base={base_damage}, strength_bonus={strength_bonus}, "
                f"modifier={modifiers['damage_multiplier']}, reduction={damage_reduction}, "
                f"final={final_damage}"
            )
            
            return final_damage

        except Exception as e:
            logging.error(f"Error calculating damage: {e}")
            return 1

    def calculate_mob_damage(self, mob: Dict, player: Dict) -> int:
        """Calculate damage for mob attacks."""
        try:
            # Get mob's base stats
            ferocity = mob['stats'].get('Ferocity', 3)
            
            # Base damage range based on ferocity
            min_damage = ferocity
            max_damage = ferocity * 2
            base_damage = random.randint(min_damage, max_damage)
            
            # Get combat modifiers
            modifiers = self.calculate_combat_modifiers(mob, player)
            
            # Calculate total damage
            total_damage = base_damage * modifiers['damage_multiplier']
            
            # Apply player's defense and tenacity
            defense = player['stats'].get('Defense', 0)
            tenacity = player['stats'].get('Tenacity', 0)
            damage_reduction = defense + (tenacity // 2)
            
            # Calculate final damage (minimum 1)
            final_damage = max(1, int(total_damage - damage_reduction))
            
            # Handle critical hit message if applicable
            if modifiers['is_critical']:
                self.apply_combat_message(
                    f"{mob['name']} lands a critical hit! ({final_damage} damage)",
                    client_socket,
                    is_critical=True
                )
                
            return final_damage

        except Exception as e:
            logging.error(f"Error calculating mob damage: {e}")
            return 1

    def check_for_level_up(self, character: Dict, client_socket: Any, account_manager: Any):
        """Check if character has gained enough experience to level up."""
        try:
            current_level = character.get('level', 1)
            current_exp = character.get('experience', 0)
            
            # Calculate experience needed for next level
            exp_needed = self.calculate_exp_needed(current_level + 1)
            
            # Check for multiple level ups
            while current_exp >= exp_needed and current_level < 10:  # Max level 10
                # Level up
                character['level'] += 1
                character['experience'] -= exp_needed
                current_level = character['level']
                
                # Increase stats
                self.apply_level_up_stats(character)
                
                # Notify player
                client_socket.sendall(
                    f"Congratulations! You have reached level {character['level']}!\n".encode()
                )
                
                # Calculate exp needed for next level
                exp_needed = self.calculate_exp_needed(current_level + 1)
                current_exp = character['experience']
            
            # Save character changes
            account_manager.update_character(character['username'], character)
            
            logging.info(
                f"Level up check completed for {character['name']} - "
                f"Level: {character['level']}, Exp: {character['experience']}"
            )

        except Exception as e:
            logging.error(f"Error checking for level up: {e}")
    
    def calculate_exp_needed(self, level: int) -> int:
        """Calculate experience needed for next level."""
        return 100 + (level - 1) * 50

    def apply_level_up_stats(self, character: Dict):
        """Apply stat increases for level up."""
        try:
            # Base stat increases
            character['stats']['Max_HP'] += 5
            character['stats']['Max_SP'] += 2
            
            # Primary stats
            character['stats']['Strength'] += 1
            character['stats']['Tenacity'] += 1
            character['stats']['Agility'] += 1
            
            # Restore HP and SP to new maximum
            character['stats']['HP'] = character['stats']['Max_HP']
            character['stats']['SP'] = character['stats']['Max_SP']
            
            # Update base stats for reference
            character['base_stats']['Max_HP'] = character['stats']['Max_HP']
            character['base_stats']['Max_SP'] = character['stats']['Max_SP']
            character['base_stats']['Strength'] += 1
            character['base_stats']['Tenacity'] += 1
            character['base_stats']['Agility'] += 1
            
            logging.debug(
                f"Applied level up stats for {character['name']} - "
                f"New Max HP: {character['stats']['Max_HP']}, "
                f"New Max SP: {character['stats']['Max_SP']}"
            )

        except Exception as e:
            logging.error(f"Error applying level up stats: {e}")

class CombatSkillHandler:
    """Handles skill usage during combat."""
    
    def __init__(self, combat_manager):
        self.combat_manager = combat_manager
        self.skill_cooldowns = {}
        
    def use_skill(self, skill: Dict, character: Dict, target: Dict, client_socket: Any):
        """Execute a skill during combat."""
        try:
            # Check cooldown
            if not self.check_cooldown(character['name'], skill['name']):
                client_socket.sendall(f"{skill['name']} is still on cooldown.\n".encode())
                return False
                
            # Check resource cost
            if not self.check_resource_cost(character, skill):
                client_socket.sendall("Not enough resources to use this skill.\n".encode())
                return False
                
            # Apply skill effects
            for effect in skill.get('effects', []):
                self.apply_skill_effect(effect, character, target, client_socket)
                
            # Start cooldown
            self.start_cooldown(character['name'], skill['name'], skill.get('cooldown', 0))
            
            return True
            
        except Exception as e:
            logging.error(f"Error using skill {skill['name']}: {e}")
            return False
            
    def check_cooldown(self, character_name: str, skill_name: str) -> bool:
        if character_name not in self.skill_cooldowns:
            return True
            
        if skill_name not in self.skill_cooldowns[character_name]:
            return True
            
        return time.time() >= self.skill_cooldowns[character_name][skill_name]
        
    def start_cooldown(self, character_name: str, skill_name: str, duration: int):
        if character_name not in self.skill_cooldowns:
            self.skill_cooldowns[character_name] = {}
            
        self.skill_cooldowns[character_name][skill_name] = time.time() + duration
        
    def check_resource_cost(self, character: Dict, skill: Dict) -> bool:
        resource_type = skill.get('resource_type', 'SP')
        cost = skill.get('resource_cost', 0)
        
        current = character['stats'].get(resource_type, 0)
        return current >= cost
        
    def apply_skill_effect(self, effect: Dict, source: Dict, target: Dict, client_socket: Any):
        effect_type = effect.get('type')
        value = effect.get('value', 0)
        
        if effect_type == 'damage':
            # Apply damage with skill bonus
            base_damage = value
            bonus_damage = source['stats'].get('Intelligence', 0) // 2
            total_damage = base_damage + bonus_damage
            
            self.combat_manager.apply_damage(target, total_damage, client_socket)
            
        elif effect_type in ['buff', 'debuff']:
            # Add effect to combat session
            duration = effect.get('duration', 30)
            stat = effect.get('stat')
            
            combat_session = self.combat_manager.get_combat_session(source['name'])
            if combat_session:
                self.combat_manager.add_combat_effect(
                    combat_session=combat_session,
                    effect_type=effect_type,
                    target=target if effect_type == 'debuff' else source,
                    value=value,
                    duration=duration,
                    name=effect.get('name', f"{effect_type.title()} Effect"),
                    client_socket=client_socket
                )

class CombatCommands:
    """Handles additional combat commands."""
    
    def __init__(self, combat_manager):
        self.combat_manager = combat_manager
        
    def handle_status(self, character: Dict, client_socket: Any):
        """Show combat status information."""
        try:
            combat_session = self.combat_manager.get_combat_session(character['name'])
            if not combat_session:
                client_socket.sendall("You are not in combat.\n".encode())
                return
                
            attacker = combat_session['attacker']
            defender = combat_session['defender']
            
            # Format status message
            status = (
                f"Combat Status - Round {combat_session['round']}\n"
                f"Your HP: {attacker['stats']['HP']}/{attacker['stats'].get('Max_HP', 0)}\n"
                f"{defender['name']}'s HP: {defender['stats']['HP']}/"
                f"{defender['stats'].get('Max_HP', 0)}\n"
            )
            
            # Add active effects
            if combat_session['status_effects']:
                status += "\nActive Effects:\n"
                for effect in combat_session['status_effects']:
                    remaining = effect['end_time'] - time.time()
                    status += f"- {effect['name']}: {remaining:.1f}s remaining\n"
            
            client_socket.sendall(status.encode())
            
        except Exception as e:
            logging.error(f"Error showing combat status: {e}")
            client_socket.sendall("Error displaying combat status.\n".encode())

class CombatInitializer:
    """Handles combat initialization and cleanup."""
    
    @staticmethod
    def initialize_combat_stats(character: Dict):
        """Initialize or reset combat statistics."""
        if 'combat_stats' not in character:
            character['combat_stats'] = {
                'total_kills': 0,
                'total_deaths': 0,
                'damage_dealt': 0,
                'damage_taken': 0,
                'crits_landed': 0,
                'successful_flees': 0
            }
            
    @staticmethod
    def create_combat_session(attacker: Dict, defender: Dict, 
                            defender_entry: Dict = None) -> Dict:
        """Create a new combat session."""
        return {
            'attacker': attacker,
            'defender': defender,
            'defender_entry': defender_entry,
            'start_time': time.time(),
            'last_attack': 0,
            'round': 0,
            'status_effects': []
        }
        
    @staticmethod
    def cleanup_combat(character: Dict, room_manager: Any = None):
        """Clean up after combat ends."""
        try:
            character['in_combat'] = False
            if room_manager and character.get('room'):
                room = room_manager.get_room(character['room'])
                if room:
                    # Update room state if needed
                    pass
                    
        except Exception as e:
            logging.error(f"Error cleaning up combat: {e}")

class CombatUtility:
    @staticmethod
    def calculate_dodge_chance(agility: int) -> float:
        return min(50, agility * 0.5)

    @staticmethod
    def calculate_crit_chance(agility: int, strength: int) -> float:
        return min(30, agility * 0.2 + strength * 0.1)

    @staticmethod
    def calculate_crit_multiplier(strength: int) -> float:
        return 1.5 + (strength * 0.01)

    @staticmethod
    def calculate_hit_chance(attacker_skill: int, defender_evasion: int) -> float:
        return max(50, 100 - (defender_evasion - attacker_skill) * 2)

def handle_attack(combat_session: Dict, client_socket: Any, room_manager: Any, mob_manager: Any, account_manager: Any, item_manager: Any):
    """Handle the attack action during combat."""
    try:
        attacker = combat_session['attacker']
        defender = combat_session['defender']

        # Calculate damage
        damage = calculate_damage(attacker, defender)

        # Apply damage to defender
        apply_damage(defender, damage, client_socket)

        # Check if defender is defeated
        if defender['stats']['HP'] <= 0:
            handle_combat_victory(combat_session, client_socket, room_manager, mob_manager, account_manager, item_manager)
            return

        # Mob counterattack
        if defender['stats']['HP'] > 0 and can_attack(defender, attacker):
            mob_damage = calculate_mob_damage(defender, attacker)
            apply_damage(attacker, mob_damage, client_socket, is_mob=True)

            # Check if attacker is defeated
            if attacker['stats']['HP'] <= 0:
                handle_player_death(combat_session, client_socket, account_manager)
                return

        # Schedule next round if combat continues
        if (combat_session['attacker']['stats']['HP'] > 0 and 
            combat_session['defender']['stats']['HP'] > 0):
            threading.Timer(
                2.0,  # Combat round delay
                process_combat_round,
                args=[combat_session, client_socket, room_manager, 
                      mob_manager, account_manager, item_manager]
            ).start()

    except Exception as e:
        logging.error(f"Error in handle_attack: {e}")
        handle_combat_error(combat_session, client_socket)




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

                agility = character['stats'].get('Agility', 0)
                base_chance = 40
                flee_chance = min(80, base_chance + (agility * 2))

                if random.uniform(0, 100) <= flee_chance:
                    available_exits = list(current_room['exits'].items())
                    direction, new_room_vnum = random.choice(available_exits)

                    old_room_vnum = character['room']
                    room_manager.remove_player_from_room(old_room_vnum, character['username'])
                    room_manager.add_player_to_room(new_room_vnum, character['username'], character['name'])

                    character['room'] = new_room_vnum
                    character['in_combat'] = False
                    account_manager.update_character(character['username'], character)

                    self.end_combat(combat_session)

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
                logging.error(f"Error in handle_flee for character {character['name']}: {e}", exc_info=True)
                client_socket.sendall(b"An error occurred while trying to flee.\n")
                return False

    def initiate_combat(self, character: Dict, target_name: str, client_socket: Any,
                       room_manager: Any, mob_manager: Any, account_manager: Any,
                       item_manager: Any) -> bool:
        with self.combat_lock:
            try:
                if character['name'] in self.active_combats:
                    client_socket.sendall(b"You're already in combat!\n")
                    return False

                current_room = room_manager.get_room(character.get('room'))
                if not current_room:
                    client_socket.sendall(b"You are in an unknown place.\n")
                    return False

                target_mob_instance = None
                for mob_entry in current_room.get('mobs', []):
                    if mob_entry.get('is_template', False):
                        continue

                    base_mob_data = mob_manager.get_mob_by_vnum(mob_entry['vnum'])
                    if base_mob_data and target_name.lower() in base_mob_data['name'].lower():
                        target_mob_instance = copy.deepcopy(base_mob_data)
                        target_mob_instance['instance_id'] = mob_entry.get('instance_id')
                        target_mob_instance['stats']['HP'] = target_mob_instance['stats'].get('HP', target_mob_instance['stats'].get('Max_HP', 100))
                        break

                if not target_mob_instance:
                    client_socket.sendall(f"You don't see '{target_name}' here.\n".encode())
                    return False

                if target_mob_instance['stats']['HP'] <= 0:
                    client_socket.sendall(b"That creature is already dead.\n")
                    return False

                character['in_combat'] = True

                combat_session = {
                    'attacker': character,
                    'defender': target_mob_instance,
                    'start_time': time.time(),
                    'last_attack': 0,
                    'round': 0,
                    'status_effects': []
                }

                self.active_combats[character['name']] = combat_session
                logging.info(f"Combat initiated between {character['name']} and {target_mob_instance['name']} ({target_mob_instance.get('instance_id')})")

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
                logging.error(f"Error initiating combat for character {character['name']}: {e}", exc_info=True)
                character['in_combat'] = False
                client_socket.sendall(b"An error occurred while initiating combat.\n")
                return False

    def process_combat_round(self, combat_session: Dict, client_socket: Any,
                           room_manager: Any, mob_manager: Any,
                           account_manager: Any, item_manager: Any):
        try:
            attacker = combat_session['attacker']
            defender = combat_session['defender']

            if not attacker or not defender or attacker['stats']['HP'] <= 0 or defender['stats']['HP'] <= 0 :
                logging.warning(f"process_combat_round called with invalid combatants for {attacker.get('name', 'Unknown')}. Ending combat.")
                self.end_combat(combat_session)
                return

            combat_session['round'] += 1
            logging.debug(f"Combat round {combat_session['round']} for {attacker['name']} vs {defender['name']}")

            self.process_status_effects(combat_session, client_socket)
            if attacker['stats']['HP'] <= 0 or defender['stats']['HP'] <= 0: return

            if self.should_mob_flee(defender):
                if self.handle_mob_flee(defender, combat_session, client_socket, room_manager, mob_manager):
                    return

            if self.can_attack(attacker, defender, client_socket):
                damage = self.calculate_damage(attacker, defender, client_socket)
                self.apply_damage(defender, damage, client_socket, attacker=attacker)

                if defender['stats']['HP'] <= 0:
                    self.handle_combat_victory(combat_session, client_socket, room_manager, mob_manager, account_manager, item_manager)
                    return

            if defender['stats']['HP'] > 0 and self.can_attack(defender, attacker, client_socket):
                mob_damage = self.calculate_mob_damage(defender, attacker, client_socket)
                self.apply_damage(attacker, mob_damage, client_socket, attacker=defender, is_mob=True)

                if attacker['stats']['HP'] <= 0:
                    self.handle_player_death(combat_session, client_socket, account_manager)
                    return

            if attacker['stats']['HP'] > 0 and defender['stats']['HP'] > 0:
                 if attacker['name'] in self.active_combats:
                    threading.Timer(
                        2.0,
                        self.process_combat_round,
                        args=[combat_session, client_socket, room_manager,
                              mob_manager, account_manager, item_manager]
                    ).start()
                 else:
                    logging.debug(f"Combat session for {attacker['name']} no longer active after round processing.")
            else:
                logging.warning(f"Combat round for {attacker['name']} ended with one combatant at <=0 HP but not handled by specific functions.")
                self.end_combat(combat_session)
        except Exception as e:
            logging.error(f"Error in combat round for {combat_session.get('attacker',{}).get('name','Unknown')}: {e}", exc_info=True)
            self.handle_combat_error(combat_session, client_socket)

    def should_mob_flee(self, mob: Dict) -> bool:
        try:
            if mob.get('is_aggressive', False) or mob.get('does_not_flee', False):
                return False
            current_hp = mob['stats']['HP']
            max_hp = mob['stats'].get('Max_HP', 1)
            if max_hp == 0: return False
            flee_threshold = mob.get('flee_threshold', 20)
            return (current_hp / max_hp * 100) <= flee_threshold
        except Exception as e:
            logging.error(f"Error checking if mob should flee: {e}", exc_info=True)
            return False

    def handle_mob_flee(self, mob: Dict, combat_session: Dict,
                       client_socket: Any, room_manager: Any, mob_manager: Any) -> bool:
        try:
            current_room_vnum = mob.get('room')
            if not current_room_vnum:
                logging.error(f"Mob {mob.get('name')} has no room vnum, cannot flee.")
                return False

            current_room = room_manager.get_room(current_room_vnum)
            if not current_room or not current_room.get('exits'):
                return False

            direction, new_room_vnum = random.choice(list(current_room['exits'].items()))
            mob_instance_id = mob.get('instance_id')

            logging.debug(f"Mob {mob['name']} ({mob_instance_id}) attempting to flee from {current_room_vnum} to {new_room_vnum}.")
            if mob_manager.move_mob(mob_instance_id, current_room_vnum, new_room_vnum, room_manager):
                attacker = combat_session['attacker']
                attacker['in_combat'] = False

                client_socket.sendall(f"{mob['name']} flees to the {direction}!\n".encode())
                logging.info(f"Mob {mob['name']} ({mob_instance_id}) fled from {current_room_vnum} to {new_room_vnum}. Combat ended for {attacker['name']}.")
                self.end_combat(combat_session)
                return True
            else:
                logging.warning(f"Mob {mob['name']} ({mob_instance_id}) failed to move via mob_manager.move_mob for fleeing.")
                return False
        except Exception as e:
            logging.error(f"Error handling mob flee: {e}", exc_info=True)
            return False

    def handle_combat_error(self, combat_session: Dict, client_socket: Any):
        try:
            attacker_name = combat_session.get('attacker', {}).get('name', 'Unknown Player')
            logging.error(f"Handling combat error for {attacker_name}.")
            if client_socket and client_socket.fileno() != -1:
                 client_socket.sendall(b"An error occurred during combat. Combat has been ended.\n")
        except Exception as e_sock:
            logging.error(f"Error sending message during handle_combat_error: {e_sock}")
        finally:
            self.end_combat(combat_session)

    def handle_combat_victory(self, combat_session: Dict, client_socket: Any,
                         room_manager: Any, mob_manager: Any,
                         account_manager: Any, item_manager: Any):
        character = combat_session['attacker']
        mob = combat_session['defender']
        instance_id = mob.get('instance_id')
        room_vnum = mob.get('room', character.get('room'))

        if not isinstance(character, dict) or not isinstance(mob, dict):
            logging.error("Invalid character or mob data in combat_session for handle_combat_victory.")
            self.end_combat(combat_session)
            return

        character_name = character.get('name', 'Unknown Player')
        mob_name = mob.get('name', 'Unknown Mob')

        try:
            logging.info(f"Combat victory for {character_name} against {mob_name} ({instance_id}) in room {room_vnum}.")

            exp_gain = mob.get('exp', 0) # Get experience before potential errors below

            if not instance_id:
                logging.error(f"Combat victory: No instance ID for {mob_name}. Cannot process mob death.")
                if client_socket.fileno() != -1: client_socket.sendall(b"Error: Could not identify the defeated enemy properly.\n")
            elif not room_vnum:
                logging.error(f"Combat victory: No room vnum for {mob_name} ({instance_id}). Character {character_name} is in {character.get('room')}. Cannot process mob death.")
                if client_socket.fileno() != -1: client_socket.sendall(b"Error: Could not determine enemy location for cleanup.\n")

            # Grant experience regardless of minor mob data issues if exp is defined
            if exp_gain > 0:
                character['experience'] = character.get('experience', 0) + exp_gain
                if client_socket.fileno() != -1: client_socket.sendall(
                    f"You have defeated {mob_name} and gained {exp_gain} experience!\n".encode()
                )
                self.check_for_level_up(character, client_socket, account_manager)
            elif instance_id and room_vnum : # Only send basic defeat message if no exp and mob data is fine
                if client_socket.fileno() != -1: client_socket.sendall(
                    f"You have defeated {mob_name}!\n".encode()
                )

            # Proceed with mob death handling only if instance_id and room_vnum are valid
            if instance_id and room_vnum:
                logging.info(f"Attempting to call mob_manager.handle_mob_death for mob {instance_id} in room {room_vnum}, killed by {character_name}.")
                death_handled_successfully = False
                try:
                    # Pass character_name to handle_mob_death
                    death_handled_successfully = self.mob_manager.handle_mob_death(
                        instance_id, room_vnum, room_manager, item_manager, character_name
                    )
                    if death_handled_successfully:
                        logging.info(f"Successfully handled death for mob instance {instance_id}.")
                    else:
                        logging.warning(f"mob_manager.handle_mob_death for {instance_id} returned False.")
                except Exception as e_death:
                    logging.error(f"Exception during mob_manager.handle_mob_death for instance {instance_id} in room {room_vnum}: {e_death}", exc_info=True)
                    if client_socket.fileno() != -1: client_socket.sendall(b"An error occurred during enemy cleanup.\n")
            else:
                logging.warning(f"Skipped mob death handling for {mob_name} due to missing instance_id or room_vnum.")

        except Exception as e_victory:
            logging.error(f"Error in handle_combat_victory main logic for {character_name} vs {mob_name}: {e_victory}", exc_info=True)
            if client_socket.fileno() != -1: client_socket.sendall(b"An unexpected error occurred processing your victory.\n")
        finally:
            logging.debug(f"Calling end_combat for {character_name} from finally block in handle_combat_victory.")
            self.end_combat(combat_session)

    def end_combat(self, combat_session: Dict):
        with self.combat_lock:
            try:
                attacker = combat_session.get('attacker')
                if not attacker or not isinstance(attacker, dict):
                    logging.error("end_combat called with invalid or missing attacker in combat_session.")
                    return

                attacker_name = attacker.get('name')
                if not attacker_name:
                    logging.error("end_combat: Attacker name is missing. Cannot reliably end combat session.")
                    return

                attacker['in_combat'] = False

                if attacker_name in self.active_combats:
                    del self.active_combats[attacker_name]
                    logging.info(f"Combat ended for {attacker_name}. Session removed from active_combats.")
                else:
                    logging.warning(f"Attempted to end combat for {attacker_name}, but no active session found for them.")

                if 'status_effects' in combat_session and isinstance(combat_session['status_effects'], list):
                    combat_session['status_effects'].clear()
            except KeyError as ke:
                logging.error(f"KeyError in end_combat: {ke}. Session: {combat_session}", exc_info=True)
            except Exception as e:
                logging.error(f"General error in end_combat: {e}. Session: {combat_session}", exc_info=True)

    def generate_loot(self, mob, corpse):
        try:
            loot_pool = mob.get('loot_pool', [])
            for loot_entry in loot_pool:
                try:
                    if not all(key in loot_entry for key in ['type', 'vnum', 'drop_rate']):
                        logging.warning(f"Invalid loot entry found: {loot_entry}")
                        continue
                    drop_rate = float(loot_entry.get('drop_rate', 0))
                    if random.uniform(0, 100) <= drop_rate:
                        loot_item = {'vnum': loot_entry['vnum'], 'type': loot_entry['type'], 'quantity': int(loot_entry.get('quantity', 1))}
                        corpse['contents'].append(loot_item)
                        logging.debug(f"Added loot item to corpse: {loot_item}")
                except (ValueError, TypeError) as e_loot_entry:
                    logging.error(f"Error processing loot entry {loot_entry}: {e_loot_entry}", exc_info=True)
                    continue
            try:
                gold_base = int(mob.get('gold', 0))
                if gold_base > 0:
                    min_gold = max(1, int(gold_base * 0.5))
                    max_gold = int(gold_base * 1.5);
                    if max_gold < min_gold: max_gold = min_gold
                    gold_amount = random.randint(min_gold, max_gold)
                    if gold_amount > 0:
                        corpse['contents'].append({'vnum': 'gold', 'type': 'currency', 'quantity': gold_amount})
                        logging.debug(f"Added {gold_amount} gold to corpse")
            except (ValueError, TypeError) as e_gold:
                logging.error(f"Error processing gold drop for mob {mob.get('name')}: {e_gold}", exc_info=True)
        except Exception as e:
            logging.error(f"Error generating loot for mob {mob.get('name')}: {e}", exc_info=True)

    def apply_damage(self, target: Dict, damage: int, client_socket: Any, attacker: Dict = None, is_mob: bool = False):
        try:
            target_name = target.get('name', 'Unknown Target')
            old_hp = target['stats']['HP']
            target['stats']['HP'] = max(0, old_hp - damage)
            actual_damage_taken = old_hp - target['stats']['HP']
            damage_info_message = f" for {actual_damage_taken} damage" # Use actual_damage_taken

            full_message = ""
            if is_mob and attacker:
                attacker_name = attacker.get('name', 'A creature')
                full_message = f"{attacker_name} hits you{damage_info_message}!\n"
                full_message += self.format_player_stats(target)
            elif attacker:
                attacker_name = attacker.get('name', 'You')
                full_message = f"You hit {target_name}{damage_info_message}!\n"
                full_message += self.format_player_stats(attacker)
            else:
                full_message = f"{target_name} takes {actual_damage_taken} damage!\n"

            if client_socket and client_socket.fileno() != -1:
                 client_socket.sendall(full_message.encode())
            logging.debug(f"{attacker.get('name', 'Source') if attacker else 'Source'} dealt {damage} (actual: {actual_damage_taken}) to {target_name}. HP: {old_hp} -> {target['stats']['HP']}")
        except Exception as e:
            logging.error(f"Error applying damage: {e}", exc_info=True)

    def format_player_stats(self, character: Dict) -> str:
        try:
            stats = character.get('stats', {})
            max_hp = stats.get('Max_HP', 1); max_sp = stats.get('Max_SP', 1); max_ap = stats.get('Max_AP', 1)
            if max_hp == 0: max_hp = 1; If max_sp == 0: max_sp = 1; if max_ap == 0: max_ap = 1
            hp_p = (stats.get('HP',0)/max_hp)*100; sp_p = (stats.get('SP',0)/max_sp)*100; ap_p = (stats.get('AP',0)/max_ap)*100
            def gc(p): return "\033[32m" if p > 66 else ("\033[33m" if p > 33 else "\033[31m") # get_color
            R = "\033[0m" # RESET
            return (f"{gc(hp_p)}HP: {stats.get('HP',0)}/{max_hp}{R} | {gc(sp_p)}SP: {stats.get('SP',0)}/{max_sp}{R} | {gc(ap_p)}AP: {stats.get('AP',0)}/{max_ap}{R}\n")
        except Exception as e: logging.error(f"Error formatting stats for {character.get('name','Unknown')}: {e}", exc_info=True); return "Stats Error\n"

    def process_status_effects(self, combat_session: Dict, client_socket: Any):
        try:
            current_time = time.time()
            for effect in list(combat_session.get('status_effects', [])):
                target_id = effect.get('target_id'); target_entity = None
                if combat_session.get('attacker',{}).get('instance_id', combat_session.get('attacker',{}).get('name')) == target_id: target_entity = combat_session['attacker']
                elif combat_session.get('defender',{}).get('instance_id', combat_session.get('defender',{}).get('name')) == target_id: target_entity = combat_session['defender']
                if not target_entity: combat_session['status_effects'].remove(effect); continue
                if current_time >= effect['end_time']: self.remove_status_effect(combat_session, effect, client_socket, target_entity)
                else: self.apply_status_effect_tick(effect, target_entity, client_socket)
        except Exception as e: logging.error(f"Error processing status effects: {e}", exc_info=True)

    def apply_status_effect_tick(self, effect: Dict, target: Dict, client_socket: Any):
        try:
            effect_type = effect.get('type'); value = effect.get('value', 0); target_name = target.get('name', 'Someone')
            if target['stats']['HP'] <= 0: return
            if effect_type == EffectType.DOT:
                target['stats']['HP'] = max(0, target['stats']['HP'] - value)
                if client_socket.fileno() != -1: client_socket.sendall(f"{effect.get('name', 'Effect')} deals {value} damage to {target_name}.\n".encode())
            elif effect_type == EffectType.HOT:
                if target['stats']['HP'] < target['stats'].get('Max_HP', target['stats']['HP']):
                    target['stats']['HP'] = min(target['stats'].get('Max_HP'), target['stats']['HP'] + value)
                    if client_socket.fileno() != -1: client_socket.sendall(f"{effect.get('name', 'Effect')} heals {target_name} for {value} HP.\n".encode())
            logging.debug(f"Tick for {effect_type} '{effect.get('name')}' on {target_name}")
        except Exception as e: logging.error(f"Error in status effect tick '{effect.get('name')}': {e}", exc_info=True)

    def add_combat_effect(self, combat_session: Dict, effect_type: str, target: Dict, value: int, duration: int, name: str = None, stat_to_change: Optional[str] = None, client_socket: Any = None):
        try:
            target_id = target.get('instance_id', target.get('name')); target_name = target.get('name', 'Someone')
            effect = {'type': effect_type, 'target_id': target_id, 'value': value, 'start_time': time.time(),
                      'end_time': time.time() + duration, 'name': name or effect_type.title(), 'stat_changed': stat_to_change}
            if effect_type == EffectType.BUFF and stat_to_change:
                target['stats'][stat_to_change] = target['stats'].get(stat_to_change, 0) + value
                if client_socket.fileno() != -1: client_socket.sendall(f"{target_name} gains {value} {stat_to_change} from {effect['name']}!\n".encode())
            elif effect_type == EffectType.DEBUFF and stat_to_change:
                target['stats'][stat_to_change] = target['stats'].get(stat_to_change, 0) - value
                if client_socket.fileno() != -1: client_socket.sendall(f"{target_name} loses {value} {stat_to_change} due to {effect['name']}!\n".encode())
            combat_session.setdefault('status_effects', []).append(effect)
            logging.debug(f"Added {effect_type} effect '{effect['name']}' to {target_name}")
            return True
        except Exception as e: logging.error(f"Error adding combat effect: {e}", exc_info=True); return False

    def remove_status_effect(self, combat_session: Dict, effect: Dict, client_socket: Any = None, target_entity: Optional[Dict] = None):
        try:
            target = target_entity
            if not target:
                target_id = effect.get('target_id')
                if combat_session.get('attacker',{}).get('instance_id', combat_session.get('attacker',{}).get('name')) == target_id: target = combat_session['attacker']
                elif combat_session.get('defender',{}).get('instance_id', combat_session.get('defender',{}).get('name')) == target_id: target = combat_session['defender']
            if not target:
                if effect in combat_session.get('status_effects', []): combat_session['status_effects'].remove(effect)
                return
            target_name = target.get('name', 'Someone'); stat_changed = effect.get('stat_changed'); value = effect.get('value',0)
            if effect.get('type') == EffectType.BUFF and stat_changed: target['stats'][stat_changed] = target['stats'].get(stat_changed, 0) - value
            elif effect.get('type') == EffectType.DEBUFF and stat_changed: target['stats'][stat_changed] = target['stats'].get(stat_changed, 0) + value
            if client_socket.fileno() != -1: client_socket.sendall(f"{effect['name']} fades from {target_name}.\n".encode())
            if effect in combat_session.get('status_effects', []): combat_session['status_effects'].remove(effect)
            logging.debug(f"Removed {effect.get('type')} effect '{effect.get('name')}' from {target_name}")
        except Exception as e: logging.error(f"Error removing status effect '{effect.get('name')}': {e}", exc_info=True)

    def calculate_combat_modifiers(self, attacker: Dict, defender: Dict) -> dict:
        mods = {'is_critical': False, 'is_dodge': False, 'damage_multiplier': 1.0, 'hit_chance': 100.0}
        try:
            if random.uniform(0,100) <= CombatUtility.calculate_dodge_chance(defender['stats'].get('Agility',0)): mods['is_dodge']=True; return mods
            str_a = attacker['stats'].get('Strength',0); agi_a = attacker['stats'].get('Agility',0)
            if random.uniform(0,100) <= CombatUtility.calculate_crit_chance(agi_a, str_a): mods['is_critical']=True; mods['damage_multiplier']=CombatUtility.calculate_crit_multiplier(str_a)
            mods['hit_chance'] = CombatUtility.calculate_hit_chance(attacker['stats'].get('Strength',0), defender['stats'].get('Evasiveness',0))
        except Exception as e: logging.error(f"Error in calc_combat_modifiers: {e}", exc_info=True)
        return mods

    def apply_combat_message(self, msg: str, cs: Any, crit: bool=False, dodge: bool=False): # Shorter params
        try:
            prefix = "CRITICAL! " if crit else ("DODGE! " if dodge else "")
            if cs and cs.fileno() != -1: cs.sendall(f"{prefix}{msg}\n".encode())
        except Exception as e: logging.error(f"Error sending combat message: {e}", exc_info=True)

    def can_attack(self, attacker: Dict, defender: Dict, client_socket: Any = None) -> bool:
        try:
            mods = self.calculate_combat_modifiers(attacker, defender)
            if mods['is_dodge']:
                if client_socket: self.apply_combat_message(f"{defender.get('name','Someone')} dodges your attack!", client_socket, is_dodge=True)
                return False
            if random.uniform(0, 100) > mods['hit_chance']:
                if client_socket: self.apply_combat_message(f"You miss {defender.get('name','Someone')}!", client_socket)
                return False
            return True
        except Exception as e: logging.error(f"Error in can_attack: {e}", exc_info=True); return False

    def calculate_damage(self, attacker: Dict, defender: Dict, client_socket: Any = None) -> int:
        try:
            w = attacker.get('equipment', {}).get('mainhand'); md = w.get('min_damage',1) if w else 1; Mxd = w.get('max_damage',max(md,2)) if w else max(md,2)
            bd = random.randint(md,Mxd); sb = attacker['stats'].get('Strength',0)//2
            mods = self.calculate_combat_modifiers(attacker,defender);
            if mods['is_dodge']: return 0
            td_p = (bd+sb)*mods['damage_multiplier'] # total_damage_potential
            dr = defender['stats'].get('Defense',0) + (defender['stats'].get('Tenacity',0)//2) # damage_reduction
            fd = max(0, int(td_p - dr)) # final_damage
            logging.debug(f"DmgCalc {attacker.get('name')}: base={bd}, str_b={sb}, crit_m={mods['damage_multiplier']:.2f}, pot={td_p:.0f}, def_r={dr}, final={fd}")
            return fd
        except Exception as e: logging.error(f"Error in calc_damage: {e}", exc_info=True); return 0

    def calculate_mob_damage(self, mob: Dict, player: Dict, client_socket: Any = None) -> int:
        try:
            fer = mob['stats'].get('Ferocity',3); md = fer; Mxd = max(md, fer*2)
            bd = random.randint(md,Mxd)
            mods = self.calculate_combat_modifiers(mob,player)
            if mods['is_dodge']: return 0
            td_p = bd * mods['damage_multiplier']
            dr = player['stats'].get('Defense',0) + (player['stats'].get('Tenacity',0)//2)
            fd = max(0, int(td_p - dr))
            logging.debug(f"MobDmgCalc {mob.get('name')}: base={bd}, crit_m={mods['damage_multiplier']:.2f}, pot={td_p:.0f}, plr_r={dr}, final={fd}")
            return fd
        except Exception as e: logging.error(f"Error in calc_mob_dmg for {mob.get('name')}: {e}", exc_info=True); return 0

    def check_for_level_up(self, character: Dict, client_socket: Any, account_manager: Any):
        try:
            cl = character.get('level',1); cxp = character.get('experience',0); lup = False # current_level, current_exp, leveled_up
            while True:
                nxp = self.calculate_exp_needed(cl+1) # next_level_exp
                if cxp >= nxp and cl < 100:
                    cl+=1; cxp -= nxp; character['level']=cl; character['experience']=cxp
                    self.apply_level_up_stats(character); lup = True
                    if client_socket.fileno()!=-1:client_socket.sendall(f"Congrats! Level {cl} reached!\n".encode())
                else: break
            if lup: account_manager.update_character(character['username'],character); logging.info(f"LvlUp {character['name']}: Lvl {cl}, Exp {cxp}")
        except Exception as e: logging.error(f"Error in check_lvl_up for {character.get('name','Unknown')}: {e}", exc_info=True)

    def calculate_exp_needed(self, level: int) -> int: return 100 + (level-2)*50 if level > 1 else 100

    def apply_level_up_stats(self, character: Dict):
        try:
            s = character.get('stats',{}); bs = character.get('base_stats',{}) # stats, base_stats
            s['Max_HP'] = s.get('Max_HP',0)+10; s['Max_SP'] = s.get('Max_SP',0)+5
            s['Strength'] = s.get('Strength',0)+1; s['Tenacity'] = s.get('Tenacity',0)+1; s['Agility'] = s.get('Agility',0)+1
            s['HP'] = s['Max_HP']; s['SP'] = s['Max_SP'] # Full restore
            bs['Max_HP']=s['Max_HP']; bs['Max_SP']=s['Max_SP']; bs['Strength']=s['Strength']; bs['Tenacity']=s['Tenacity']; bs['Agility']=s['Agility']
            logging.debug(f"Applied level up stats for {character.get('name','Unknown')}")
        except Exception as e: logging.error(f"Error applying lvl_up_stats for {character.get('name','Unknown')}: {e}", exc_info=True)

    def handle_player_death(self, combat_session: Dict, client_socket: Any, account_manager: Any):
        try:
            player = combat_session['attacker']; mob = combat_session['defender']
            logging.info(f"Player {player.get('name','Unknown')} defeated by {mob.get('name','Unknown')}.")
            if client_socket.fileno()!=-1: client_socket.sendall(f"You were slain by {mob.get('name','a creature')}!\n".encode())
            player['room'] = "1"; player['stats']['HP'] = 1 # Respawn logic
            account_manager.update_character(player['username'], player)
            self.end_combat(combat_session)
            if client_socket.fileno()!=-1: client_socket.sendall(b"You are returned to the starting area.\n")
        except Exception as e:
            logging.error(f"Error in handle_player_death for {player.get('name','Unknown')}: {e}", exc_info=True)
            self.end_combat(combat_session) # Ensure combat ends
            if client_socket.fileno()!=-1: client_socket.sendall(b"Error processing defeat.\n")

class CombatSkillHandler: # Simplified stubs for brevity
    def __init__(self, combat_manager): self.combat_manager = combat_manager
class CombatCommands:  # Simplified stubs
    def __init__(self, combat_manager): self.combat_manager = combat_manager
class CombatInitializer: # Simplified stubs
    @staticmethod
    def initialize_combat_stats(character): pass
class CombatUtility: # Simplified stubs
    @staticmethod
    def calculate_dodge_chance(agility): return 0.0
    @staticmethod
    def calculate_crit_chance(agility, strength): return 0.0
    @staticmethod
    def calculate_crit_multiplier(strength): return 1.0
    @staticmethod
    def calculate_hit_chance(attacker_skill, defender_evasion): return 100.0

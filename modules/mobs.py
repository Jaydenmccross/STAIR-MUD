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
        self.respawn_queue = Queue()
        self.mob_templates = {}
        logging.debug(f"MobManager initialized with {len(self.mobs)} mob templates")
        logging.debug(f"MobManager methods: {dir(self)}")
        logging.debug(f"handle_mob_death exists: {'handle_mob_death' in dir(self)}")
        self.load_initial_state()

    def load_initial_state(self):
        try:
            rooms = self.room_manager.get_all_rooms()
            for room in rooms:
                room_vnum = str(room.get('vnum'))
                if not room_vnum: continue
                self.mob_counts.setdefault(room_vnum, {})
                self.mob_templates.setdefault(room_vnum, {})
                for mob_in_room_data in room.get('mobs', []): # Renamed mob to mob_in_room_data
                    mob_vnum = str(mob_in_room_data.get('vnum'))
                    if mob_in_room_data.get('is_template', False):
                        self.mob_templates[room_vnum][mob_vnum] = mob_in_room_data
                    else:
                        self.mob_counts[room_vnum][mob_vnum] = self.mob_counts[room_vnum].get(mob_vnum, 0) + 1
            logging.info("MobManager: Loaded initial mob state")
        except Exception as e:
            logging.error(f"Error loading initial mob state: {e}", exc_info=True)

    def get_mob_by_vnum(self, vnum):
        try:
            vnum_str = str(vnum)
            with self.lock:
                mob_data = next((m for m in self.mobs if str(m["vnum"]) == vnum_str), None)
            if mob_data:
                return copy.deepcopy(mob_data)
            logging.error(f"Mob with vnum {vnum_str} not found.")
            return None
        except Exception as e:
            logging.error(f"Error retrieving mob with vnum {vnum}: {e}", exc_info=True)
            return None

    def get_mob_by_alias(self, alias):
        alias_lower = alias.lower()
        try:
            with self.lock:
                mob_data = next((m for m in self.mobs if m.get("alias", "").lower() == alias_lower), None)
            if mob_data:
                return copy.deepcopy(mob_data)
            logging.error(f"Mob with alias '{alias_lower}' not found.")
            return None
        except Exception as e:
            logging.error(f"Error retrieving mob with alias '{alias_lower}': {e}", exc_info=True)
            return None

    def spawn_mob_in_room(self, mob_vnum, room_vnum, room_manager_param):
        with self.lock:
            try:
                mob_template = self.get_mob_by_vnum(mob_vnum)
                if not mob_template:
                    logging.error(f"No mob template found for vnum {mob_vnum}")
                    return False
                instance_id = f"{mob_vnum}_{int(time.time())}_{random.randint(1000, 9999)}"
                mob_instance = copy.deepcopy(mob_template)
                mob_instance.update({'instance_id': instance_id, 'room': room_vnum, 'is_template': False})
                self.active_mobs[instance_id] = mob_instance
                logging.debug(f"Added mob {mob_instance['name']} (ID: {instance_id}) to active_mobs")
                room_obj = room_manager_param.get_room(room_vnum)
                if not room_obj:
                    logging.error(f"Room {room_vnum} not found for spawning mob.")
                    del self.active_mobs[instance_id] # Clean up
                    return False
                room_obj.setdefault('mobs', []).append({'vnum': mob_vnum, 'instance_id': instance_id, 'is_template': False})
                self.ensure_template_in_room(room_obj, mob_template)
                room_manager_param.save_rooms()
                logging.info(f"Successfully spawned mob {mob_vnum} (ID: {instance_id}) in room {room_vnum}")
                return True
            except Exception as e:
                logging.error(f"Error spawning mob {mob_vnum} in room {room_vnum}: {e}", exc_info=True)
                return False

    def ensure_template_in_room(self, room_obj, mob_template):
        if not any(m.get('vnum') == mob_template['vnum'] and m.get('is_template', False) for m in room_obj.get('mobs', [])):
            template_entry = {'vnum': mob_template['vnum'], 'is_template': True,
                              'quantity': mob_template.get('quantity', 1),
                              'max_instances': mob_template.get('max_instances', 1)}
            room_obj.setdefault('mobs', []).append(template_entry)
            logging.info(f"Added template for mob {mob_template['vnum']} to room {room_obj.get('vnum')}")

    def remove_mob_from_room(self, instance_id, room_vnum, room_manager_param):
        with self.lock:
            try:
                room_obj = room_manager_param.get_room(room_vnum)
                if not room_obj: return False
                mob_instance = self.active_mobs.get(instance_id)
                if not mob_instance: return False
                mob_vnum = mob_instance['vnum']
                room_obj['mobs'] = [m for m in room_obj.get('mobs', []) if not (m.get('instance_id') == instance_id and not m.get('is_template'))]
                base_template = self.get_mob_by_vnum(mob_vnum)
                if base_template: self.ensure_template_in_room(room_obj, base_template)
                if instance_id in self.active_mobs: del self.active_mobs[instance_id]
                room_manager_param.save_rooms()
                logging.info(f"Removed mob instance {instance_id} from room {room_vnum}")
                return True
            except Exception as e:
                logging.error(f"Error removing mob instance {instance_id} from room {room_vnum}: {e}", exc_info=True)
                return False

    def handle_mob_death(self, instance_id: str, room_vnum: str, room_manager_param: Any, item_manager_param: Any, killed_by_char_name: str):
        logging.debug(f"Attempting to handle death of mob {instance_id} in room {room_vnum}, killed by {killed_by_char_name}")
        with self.lock:
            try:
                mob_instance = self.active_mobs.get(instance_id)
                if not mob_instance:
                    logging.error(f"No mob found for instance ID {instance_id} to handle death.")
                    return False
                room_obj = room_manager_param.get_room(room_vnum)
                if not room_obj:
                    logging.error(f"Room {room_vnum} not found for mob death {instance_id}.")
                    return False

                corpse_name = f"corpse of {mob_instance['name']}"
                corpse = {
                    'vnum': 'corpse', 'name': corpse_name, 'type': 'corpses',
                    'short_desc': f"The corpse of {mob_instance['name']} lies here.",
                    'long_desc': f"This is the corpse of {mob_instance['name']}.",
                    'decay_time': time.time() + 300, 'contents': [],
                    'killed_by': killed_by_char_name # Set killed_by
                }
                logging.debug(f"Generating loot for corpse of {mob_instance['name']} (ID: {instance_id}).")
                self.generate_corpse_loot(mob_instance, corpse)
                room_obj.setdefault('items', []).append(corpse)

                if instance_id in self.active_mobs: del self.active_mobs[instance_id]
                mob_vnum_str = str(mob_instance['vnum'])
                if room_vnum in self.mob_counts and mob_vnum_str in self.mob_counts[room_vnum]:
                    self.mob_counts[room_vnum][mob_vnum_str] = max(0, self.mob_counts[room_vnum][mob_vnum_str] - 1)
                room_obj['mobs'] = [m for m in room_obj.get('mobs', []) if m.get('instance_id') != instance_id]

                template = self.mob_templates.get(room_vnum, {}).get(mob_vnum_str)
                if not template:
                    base_mob_template = self.get_mob_by_vnum(mob_vnum_str)
                    if base_mob_template: template = base_mob_template
                    else: logging.error(f"No template found for mob {mob_vnum_str} to queue respawn.")

                if template and template.get('respawn_time'):
                    respawn_data = {
                        'mob_vnum': mob_vnum_str, 'room_vnum': room_vnum, 'template': template,
                        'respawn_time': time.time() + template.get('respawn_time', 300)
                    }
                    if self.spawn_manager:
                        self.spawn_manager.queue_respawn(respawn_data)
                    else:
                        logging.warning("Spawn manager not set in MobManager, falling back to local respawn queue.")
                        self.queue_respawn(respawn_data)
                room_manager_param.save_rooms()
                logging.info(f"Successfully handled death of mob {mob_instance['name']} (ID: {instance_id}) in room {room_vnum}.")
                return True
            except Exception as e:
                logging.error(f"Error handling mob death for instance {instance_id}: {e}", exc_info=True)
                return False

    def generate_corpse_loot(self, mob_data, corpse_data):
        try:
            loot_pool = mob_data.get('loot_pool', [])
            generated_items_count = 0
            for loot_item_template in loot_pool: # Renamed loot_item to loot_item_template
                if random.uniform(0, 100) <= loot_item_template.get('drop_rate', 0):
                    corpse_data['contents'].append({
                        'vnum': loot_item_template['vnum'],
                        'type': loot_item_template['type'],
                        'quantity': loot_item_template.get('quantity', 1)
                    })
                    generated_items_count += 1
            gold_base = mob_data.get('gold', 0)
            generated_gold_amount = 0
            if gold_base > 0:
                min_gold = max(1, int(gold_base * 0.5))
                max_gold = int(gold_base * 1.5)
                if max_gold < min_gold: max_gold = min_gold
                generated_gold_amount = random.randint(min_gold, max_gold)
                if generated_gold_amount > 0:
                    corpse_data['contents'].append({'vnum': 'gold', 'type': 'currency', 'quantity': generated_gold_amount})
            logging.debug(f"Loot generation complete for {mob_data['name']}: {generated_items_count} item types, {generated_gold_amount} gold.")
        except Exception as e:
            logging.error(f"Error generating corpse loot for {mob_data['name']}: {e}", exc_info=True)

    # ... (rest of MobManager methods remain the same) ...
    def add_mob(self, mob_data): # Renamed mob to mob_data
        """Add a new mob template."""
        try:
            with self.lock:
                if any(str(existing_mob["vnum"]) == str(mob_data["vnum"]) for existing_mob in self.mobs):
                    logging.error(f"Mob with vnum {mob_data['vnum']} already exists.")
                    return False
                self.mobs.append(mob_data)
                logging.info(f"Added mob: {mob_data['name']}")
                self.save_mobs()
                return True
        except Exception as e:
            logging.error(f"Error adding mob '{mob_data['name']}': {e}", exc_info=True)
            return False

    def remove_mob(self, vnum_str): # Renamed vnum to vnum_str
        """Remove a mob template."""
        try:
            with self.lock:
                mob_to_remove = next((m for m in self.mobs if str(m["vnum"]) == vnum_str), None)
                if mob_to_remove:
                    self.mobs.remove(mob_to_remove)
                    logging.info(f"Removed mob: {mob_to_remove['name']} with vnum: {vnum_str}")
                    self.save_mobs()
                    return True
                logging.error(f"Mob with vnum {vnum_str} does not exist.")
                return False
        except Exception as e:
            logging.error(f"Error removing mob with vnum {vnum_str}: {e}", exc_info=True)
            return False

    def save_mobs(self):
        try:
            with self.lock:
                save_json(self.mobs_file, self.mobs)
            logging.info("Mobs data saved.")
        except Exception as e:
            logging.error(f"Error saving mobs: {e}", exc_info=True)

    def get_active_mob(self, instance_id_param):
        return self.active_mobs.get(instance_id_param)

    def update_mob_stats(self, instance_id_param, new_stats_param):
        with self.lock:
            if instance_id_param in self.active_mobs:
                self.active_mobs[instance_id_param]['stats'].update(new_stats_param)
                return True
            return False

    def move_mob(self, instance_id_param, from_room_vnum, to_room_vnum, room_manager_param):
        with self.lock:
            if instance_id_param not in self.active_mobs: return False
            mob_to_move = self.active_mobs[instance_id_param]
            if not self.remove_mob_from_room(instance_id_param, from_room_vnum, room_manager_param): return False
            mob_to_move['room'] = to_room_vnum
            self.active_mobs[instance_id_param] = mob_to_move
            result = self.spawn_mob_in_room(mob_to_move['vnum'], to_room_vnum, room_manager_param)
            if not result:
                mob_to_move['room'] = from_room_vnum
                self.active_mobs[instance_id_param] = mob_to_move
                self.spawn_mob_in_room(mob_to_move['vnum'], from_room_vnum, room_manager_param)
                return False
            return True

    def calculate_mob_attack(self, mob_data): ferocity = mob_data['stats'].get('Ferocity', 3); return random.randint(ferocity, ferocity * 2)
    def calculate_mob_defense(self, mob_data): return mob_data['stats'].get('Resilience', 3)
    def calculate_mob_evasion(self, mob_data): return mob_data['stats'].get('Evasiveness', 3)
    def should_mob_flee(self, mob_data):
        if mob_data.get('is_aggressive', False): return False
        current_hp = mob_data.get('stats',{}).get('HP',0)
        max_hp = mob_data.get('stats',{}).get('Max_HP',1)
        if max_hp == 0: return False
        return (current_hp / max_hp * 100) <= mob_data.get('flee_threshold', 20)
    def generate_mob_identifier(self, mob_name_param, room_obj):
        count = sum(1 for m in room_obj.get('mobs',[]) if m.get('name') == mob_name_param) # Simplified
        return f"{mob_name_param} ({count + 1})"
    def respawn_mob_check(self, room_vnum_param, mob_vnum_param, room_manager_param):
        room_obj = room_manager_param.get_room(room_vnum_param)
        if not room_obj: return False
        mob_template = self.get_mob_by_vnum(mob_vnum_param)
        if not mob_template: return False
        current_count = sum(1 for m in room_obj.get('mobs', []) if m.get('vnum') == mob_vnum_param and not m.get('is_template'))
        if current_count < mob_template.get('max_instances', 1):
            self.spawn_mob_in_room(mob_vnum_param, room_vnum_param, room_manager_param)
            return True
        return False
    def create_instance(self, vnum_param, room_vnum_param):
        with self.lock:
            template = self.get_mob_by_vnum(vnum_param)
            if not template: return None
            instance_id = f"{vnum_param}_{int(time.time())}_{random.randint(1000, 9999)}"
            room_instance = {'vnum': vnum_param, 'instance_id': instance_id, 'is_template': False}
            full_instance = copy.deepcopy(template)
            full_instance.update({'instance_id': instance_id, 'room': room_vnum_param, 'is_template': False})
            self.active_mobs[instance_id] = full_instance
            self.mob_counts.setdefault(room_vnum_param, {})
            self.mob_counts[room_vnum_param][str(vnum_param)] = self.mob_counts[room_vnum_param].get(str(vnum_param), 0) + 1
            return room_instance
    def remove_instance(self, instance_id_param):
        with self.lock:
            if instance_id_param in self.active_mobs:
                mob_to_remove = self.active_mobs[instance_id_param]
                room_vnum = mob_to_remove['room']
                mob_vnum_str = str(mob_to_remove['vnum'])
                if room_vnum in self.mob_counts and mob_vnum_str in self.mob_counts[room_vnum]:
                    self.mob_counts[room_vnum][mob_vnum_str] = max(0, self.mob_counts[room_vnum][mob_vnum_str] - 1)
                del self.active_mobs[instance_id_param]
                return True
            return False
    def queue_respawn(self, mob_data_param: Dict):
        try:
            room_vnum = str(mob_data_param.get('room_vnum'))
            mob_vnum = str(mob_data_param.get('vnum'))
            room_obj = self.room_manager.get_room(room_vnum)
            if not room_obj: logging.error(f"Room {room_vnum} not found for respawn"); return False
            template = next((m for m in room_obj.get('mobs', []) if m.get('is_template') and str(m.get('vnum')) == mob_vnum), None)
            if not template: template = self.get_mob_by_vnum(mob_vnum)
            if not template: logging.error(f"No template for mob {mob_vnum} in room {room_vnum} or globally."); return False
            respawn_delay = template.get('respawn_time', 300)
            actual_respawn_time = time.time() + respawn_delay
            respawn_data_to_queue = {'mob_vnum': mob_vnum, 'room_vnum': room_vnum, 'template': template, 'respawn_time': actual_respawn_time}
            self.respawn_queue.put(respawn_data_to_queue)
            logging.info(f"MobManager locally queued mob {mob_vnum} for respawn at {time.ctime(actual_respawn_time)}")
            return True
        except Exception as e:
            logging.error(f"Error in MobManager queuing mob respawn: {e}", exc_info=True)
            return False
    def _handle_respawn(self, respawn_data_param: Dict):
        try:
            if time.time() < respawn_data_param['respawn_time']: self.respawn_queue.put(respawn_data_param); return
            room_vnum = str(respawn_data_param['room_vnum']); mob_vnum = str(respawn_data_param['mob_vnum']); template = respawn_data_param['template']
            with self.lock:
                current_count = self._count_mob_instances(room_vnum, mob_vnum)
                if current_count >= int(template.get('max_instances', 1)): return
                if self._spawn_mob_instance(room_vnum, template, self.room_manager):
                    logging.info(f"MobManager (local queue): Respawned mob {mob_vnum} in room {room_vnum}")
        except Exception as e: logging.error(f"Error in MobManager handling local respawn: {e}", exc_info=True)
    def _count_mob_instances(self, room_vnum_param, mob_vnum_param):
        room_obj = self.room_manager.get_room(room_vnum_param)
        if not room_obj: return 0
        return sum(1 for m in room_obj.get('mobs', []) if str(m.get('vnum')) == str(mob_vnum_param) and not m.get('is_template'))
    def _spawn_mob_instance(self, room_vnum_param, template_param, room_manager_param):
        try:
            mob_vnum = str(template_param['vnum'])
            instance_id = f"{mob_vnum}_{int(time.time())}_{random.randint(1000,9999)}"
            mob_instance_data = copy.deepcopy(template_param); mob_instance_data.update({'instance_id':instance_id, 'is_template':False, 'room':room_vnum_param})
            self.active_mobs[instance_id] = mob_instance_data
            if room_manager_param.add_mob_to_room(room_vnum_param, {'vnum': mob_vnum, 'instance_id': instance_id, 'is_template': False}):
                self.mob_counts.setdefault(room_vnum_param, {})
                self.mob_counts[room_vnum_param][mob_vnum] = self.mob_counts[room_vnum_param].get(mob_vnum, 0) + 1
                return True
            del self.active_mobs[instance_id]; return False
        except Exception as e: logging.error(f"Error in MobManager _spawn_mob_instance: {e}", exc_info=True); return False

class MobSpawnManager:
    def __init__(self, mob_manager_param, room_manager_param):
        self.mob_manager = mob_manager_param
        self.room_manager = room_manager_param
        self.running = True
        self.respawn_queue = Queue()
        self.lock = threading.RLock()
        self.spawn_thread = None
        self.active_processing_threads = set()
        self.processing_lock = threading.Lock()

    def start(self):
        if not self.running: self.running = True
        self.spawn_thread = threading.Thread(target=self._spawn_loop, daemon=True)
        self.spawn_thread.start()
        logging.info("Started mob spawn manager")

    def _spawn_loop(self):
        while self.running:
            try:
                if not self.respawn_queue.empty():
                    respawn_data = self.respawn_queue.get_nowait()
                    thread = threading.Thread(target=self._handle_respawn_thread_worker, args=(respawn_data,))
                    with self.processing_lock: self.active_processing_threads.add(thread)
                    thread.start()
                self._maintain_spawn_counts()
                with self.processing_lock:
                    finished_threads = {t for t in self.active_processing_threads if not t.is_alive()}
                    self.active_processing_threads.difference_update(finished_threads)
                time.sleep(5)
            except Exception as e:
                logging.error(f"Error in spawn loop: {e}", exc_info=True)
                time.sleep(10)

    def _handle_respawn_thread_worker(self, respawn_data):
        try: self._handle_respawn(respawn_data)
        finally:
            with self.processing_lock:
                if threading.current_thread() in self.active_processing_threads:
                    self.active_processing_threads.remove(threading.current_thread())

    def _maintain_spawn_counts(self):
        with self.lock:
            try:
                all_rooms = self.room_manager.get_all_rooms()
                for room_obj in all_rooms:
                    room_vnum = str(room_obj.get('vnum'))
                    for mob_template_in_room in room_obj.get('mobs', []):
                        if mob_template_in_room.get('is_template', False):
                            mob_vnum = str(mob_template_in_room.get('vnum'))
                            desired_count = int(mob_template_in_room.get('quantity', 1))
                            current_instances_in_room = sum(1 for m in room_obj.get('mobs',[]) if str(m.get('vnum')) == mob_vnum and not m.get('is_template'))
                            needed = max(0, desired_count - current_instances_in_room)
                            if needed > 0 :
                                for _ in range(needed): self._spawn_mob_instance(room_vnum, mob_template_in_room)
            except Exception as e: logging.error(f"Error maintaining spawn counts: {e}", exc_info=True)

    def _spawn_mob_instance(self, room_vnum_param, template_param):
        try:
            mob_vnum = str(template_param['vnum'])
            max_instances = int(template_param.get('max_instances', 1))
            room_obj = self.room_manager.get_room(room_vnum_param)
            if not room_obj: logging.error(f"Spawn: Room {room_vnum_param} not found."); return False
            current_instances_in_room = sum(1 for m in room_obj.get('mobs',[]) if str(m.get('vnum'))==mob_vnum and not m.get('is_template'))
            if current_instances_in_room >= max_instances: return False
            room_mob_entry = self.mob_manager.create_instance(mob_vnum, room_vnum_param)
            if not room_mob_entry: logging.error(f"Failed to create instance for {mob_vnum} in {room_vnum_param}."); return False
            if self.room_manager.add_mob_to_room(room_vnum_param, room_mob_entry):
                logging.info(f"MobSpawnManager: Spawned mob {mob_vnum} (ID: {room_mob_entry.get('instance_id')}) in room {room_vnum_param}")
                return True
            logging.error(f"Failed to add mob {mob_vnum} (ID: {room_mob_entry.get('instance_id')}) to room {room_vnum_param}.")
            self.mob_manager.remove_instance(room_mob_entry.get('instance_id')); return False
        except Exception as e: logging.error(f"Error in MobSpawnManager _spawn_mob_instance: {e}", exc_info=True); return False

    def queue_respawn(self, respawn_data_param: Dict):
        try:
            mob_vnum = respawn_data_param.get('mob_vnum'); room_vnum = respawn_data_param.get('room_vnum')
            template_from_death = respawn_data_param.get('template', {})
            room_obj = self.room_manager.get_room(room_vnum)
            final_template_for_respawn = template_from_death
            if room_obj:
                room_specific_template = next((m for m in room_obj.get('mobs',[]) if m.get('is_template') and str(m.get('vnum')) == str(mob_vnum)), None)
                if room_specific_template: final_template_for_respawn = room_specific_template
            if 'respawn_time' not in final_template_for_respawn: final_template_for_respawn['respawn_time'] = 300
            respawn_data_param['template'] = final_template_for_respawn
            respawn_data_param['respawn_time'] = time.time() + final_template_for_respawn['respawn_time']
            self.respawn_queue.put(respawn_data_param)
            logging.info(f"MobSpawnManager: Queued mob {mob_vnum} for respawn in {room_vnum} at {time.ctime(respawn_data_param['respawn_time'])}")
            return True
        except Exception as e: logging.error(f"Error in MobSpawnManager queuing respawn: {e}", exc_info=True); return False

    def _handle_respawn(self, respawn_data_param: Dict):
        try:
            if time.time() < respawn_data_param['respawn_time']: self.respawn_queue.put(respawn_data_param); return
            room_vnum = str(respawn_data_param['room_vnum']); template_for_spawn = respawn_data_param['template']
            mob_vnum_to_spawn = str(template_for_spawn.get('vnum'))
            if not mob_vnum_to_spawn: logging.error(f"Respawn failed: no vnum in template. Data: {respawn_data_param}"); return
            with self.lock:
                if self._spawn_mob_instance(room_vnum, template_for_spawn):
                    logging.info(f"MobSpawnManager: Respawned mob {mob_vnum_to_spawn} in room {room_vnum}")
        except Exception as e: logging.error(f"Error in MobSpawnManager handling respawn: {e}", exc_info=True)

    def stop(self):
        logging.info("Stopping mob spawn manager...")
        self.running = False
        if self.spawn_thread and self.spawn_thread.is_alive():
            self.spawn_thread.join(timeout=15.0)
            if self.spawn_thread.is_alive(): logging.warning("Spawn thread did not terminate cleanly after 15s.")
        with self.processing_lock: active_threads_copy = list(self.active_processing_threads)
        if active_threads_copy:
            logging.info(f"Waiting for {len(active_threads_copy)} active respawn processing threads...")
            for thread in active_threads_copy:
                thread.join(timeout=5.0)
                if thread.is_alive(): logging.warning(f"Respawn thread {thread.name} did not terminate cleanly.")
        logging.info("Mob spawn manager stopped.")

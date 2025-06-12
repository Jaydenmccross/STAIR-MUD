import logging
from modules.data_handler import load_json, save_json
import threading
import copy
import time
from typing import Dict, List, Optional, Set, Tuple, Any

class ItemManager:
    def __init__(self, items_file: str, weapons_file: str, armors_file: str, 
                 consumables_file: str, containers_file: str, currencies_file: str, 
                 corpses_file: str):
        """
        Initialize the ItemManager with file paths and load all items.
        """
        # File paths for different item types
        self.items_file = items_file
        self.weapons_file = weapons_file
        self.armors_file = armors_file
        self.consumables_file = consumables_file
        self.containers_file = containers_file
        self.currencies_file = currencies_file
        self.corpses_file = corpses_file
        self.lock = threading.RLock()

        # Load all items from their respective files
        self.items = self.load_items_from_file(self.items_file)
        self.weapons = self.load_items_from_file(self.weapons_file)
        self.armors = self.load_items_from_file(self.armors_file)
        self.consumables = self.load_items_from_file(self.consumables_file)
        self.containers = self.load_items_from_file(self.containers_file)
        self.currencies = self.load_items_from_file(self.currencies_file)
        self.corpses = self.load_items_from_file(self.corpses_file)

        # Cache for tracking LORE items per character
        self.character_lore_cache: Dict[str, Dict[str, int]] = {}
        
        logging.debug(f"ItemManager initialized with: {len(self.items)} items, {len(self.weapons)} weapons, "
                     f"{len(self.armors)} armors, {len(self.consumables)} consumables, "
                     f"{len(self.containers)} containers, {len(self.currencies)} currencies, "
                     f"{len(self.corpses)} corpses.")

    # LORE Item Management Methods
    def count_lore_items(self, character: Dict[str, Any], vnum: str) -> int:
        """
        Count how many instances of a LORE item a character has across all storage.
        
        Args:
            character: The character dictionary containing inventory and equipment
            vnum: The vnum of the LORE item to count
            
        Returns:
            Total count of the LORE item instances
        """
        count = 0
        
        # Check inventory
        for item in character.get('inventory', []):
            if str(item.get('vnum')) == str(vnum):
                count += 1
            # Check containers in inventory
            if item.get('type') == 'containers':
                count += self._count_lore_in_container(item, vnum)
                
        # Check equipment slots
        for slot, equipped_item in character.get('equipment', {}).items():
            if equipped_item and str(equipped_item.get('vnum')) == str(vnum):
                count += 1
                
        return count

    def _count_lore_in_container(self, container: Dict[str, Any], vnum: str) -> int:
        """
        Recursively count LORE items in a container.
        """
        count = 0
        for item in container.get('contents', []):
            if str(item.get('vnum')) == str(vnum):
                count += 1
            if item.get('type') == 'containers':
                count += self._count_lore_in_container(item, vnum)
        return count

    def can_acquire_lore_item(self, character: Dict[str, Any], item: Dict[str, Any]) -> bool:
        """
        Check if a character can acquire a LORE item.
        
        Args:
            character: The character dictionary
            item: The item dictionary to check
            
        Returns:
            bool: True if the character can acquire the item, False otherwise
        """
        if not item.get('is_lore', False):
            return True
            
        current_count = self.count_lore_items(character, item['vnum'])
        return current_count == 0

    def update_character_lore_cache(self, character: Dict[str, Any]) -> None:
        """
        Update the cache of LORE items for a character.
        """
        username = character.get('username')
        if not username:
            return
            
        self.character_lore_cache[username] = {}
        
        # Function to process an item and update cache
        def process_item(item: Dict[str, Any]) -> None:
            if item.get('is_lore', False):
                vnum = str(item.get('vnum'))
                self.character_lore_cache[username][vnum] = self.character_lore_cache[username].get(vnum, 0) + 1

        # Check inventory
        for item in character.get('inventory', []):
            process_item(item)
            # Check containers
            if item.get('type') == 'containers':
                for container_item in item.get('contents', []):
                    process_item(container_item)

        # Check equipment
        for slot, item in character.get('equipment', {}).items():
            if item:
                process_item(item)

    # Existing Methods with LORE Support Added
    def load_items_from_file(self, filename: str) -> List[Dict[str, Any]]:
        """
        Load items from a JSON file and ensure valid structure.
        """
        try:
            data = load_json(filename)
            if isinstance(data, dict):
                items = data.get('items', [])
            elif isinstance(data, list):
                items = data
            else:
                items = []
            logging.debug(f"Loaded {len(items)} items from {filename}")
            return items
        except Exception as e:
            logging.error(f"Failed to load items from {filename}: {e}")
            return []

    def get_item_by_vnum(self, vnum: str, category: str) -> Optional[Dict[str, Any]]:
        """
        Get an item by its VNUM from a specified category.
        """
        try:
            vnum_str = str(vnum)
            with self.lock:
                categories = {
                    'items': self.items,
                    'weapons': self.weapons,
                    'armors': self.armors,
                    'consumables': self.consumables,
                    'containers': self.containers,
                    'currencies': self.currencies,
                    'corpses': self.corpses
                }

                if category in categories:
                    logging.debug(f"Searching for item with vnum '{vnum_str}' in category '{category}'.")
                    items_list = categories[category]

                    for item in items_list:
                        if str(item['vnum']) == vnum_str:
                            logging.debug(f"Found item: '{item['name']}' in category '{category}'")
                            return copy.deepcopy(item)
                    logging.error(f"Item with vnum '{vnum_str}' not found in category '{category}'.")
                else:
                    logging.error(f"Category '{category}' does not exist.")
                return None
        except Exception as e:
            logging.error(f"Error retrieving item with vnum {vnum}: {e}")
            return None

    def add_item(self, item: Dict[str, Any], category: str) -> bool:
        """
        Add an item to its appropriate category.
        """
        try:
            with self.lock:
                categories = {
                    'items': self.items,
                    'weapons': self.weapons,
                    'armors': self.armors,
                    'consumables': self.consumables,
                    'containers': self.containers,
                    'currencies': self.currencies,
                    'corpses': self.corpses
                }

                if category in categories:
                    if not isinstance(item, dict):
                        logging.error(f"Item entry is not a valid dictionary: {item}")
                        return False
                    if 'name' not in item or 'vnum' not in item:
                        logging.error(f"Item entry is missing required attributes: {item}")
                        return False
                    categories[category].append(item)
                    logging.info(f"Added item: '{item['name']}' to category '{category}'.")
                    return True
                else:
                    logging.error(f"Unknown category: '{category}'.")
                    return False
        except Exception as e:
            logging.error(f"Error adding item '{item.get('name', 'Unknown')}': {e}")
            return False

    def remove_item(self, vnum: str, category: str) -> bool:
        """
        Remove an item from a specified category.
        """
        try:
            vnum_str = str(vnum)
            with self.lock:
                categories = {
                    'items': self.items,
                    'weapons': self.weapons,
                    'armors': self.armors,
                    'consumables': self.consumables,
                    'containers': self.containers,
                    'currencies': self.currencies,
                    'corpses': self.corpses
                }

                if category in categories:
                    items_list = categories[category]
                    item = next((item for item in items_list if str(item.get("vnum")) == vnum_str), None)

                    if item:
                        items_list.remove(item)
                        logging.info(f"Removed item: '{item['name']}' from category '{category}'.")
                        return True
                    else:
                        logging.error(f"Item with vnum '{vnum_str}' not found in category '{category}'.")
                else:
                    logging.error(f"Category '{category}' does not exist.")
                return False
        except Exception as e:
            logging.error(f"Error removing item with vnum {vnum}: {e}")
            return False

    def create_corpse(self, mob_name: str, killed_by: str) -> Dict[str, Any]:
        """
        Create a new corpse instance for a mob.
        """
        corpse = {
            'vnum': 'corpse',
            'name': f"corpse of {mob_name}",
            'type': 'corpses',
            'short_desc': f"The corpse of {mob_name} lies here",
            'long_desc': f"This is the corpse of {mob_name}.",
            'decay_time': time.time() + 300,
            'is_container': True,
            'contents': [],
            'killed_by': killed_by
        }
        return corpse

    def save_all_items(self) -> None:
        """
        Save all item data to their respective files.
        """
        try:
            with self.lock:
                save_json(self.items_file, self.items)
                save_json(self.weapons_file, self.weapons)
                save_json(self.armors_file, self.armors)
                save_json(self.consumables_file, self.consumables)
                save_json(self.containers_file, self.containers)
                save_json(self.currencies_file, self.currencies)
                save_json(self.corpses_file, self.corpses)
            logging.info("All items saved successfully.")
        except Exception as e:
            logging.error(f"Error saving all items: {e}")

    def validate_item_transfer(self, character: Dict[str, Any], item: Dict[str, Any], 
                             transfer_type: str = 'acquire') -> Tuple[bool, str]:
        """
        Validate if an item can be transferred (acquired/equipped/stored).
        
        Args:
            character: The character dictionary
            item: The item to validate
            transfer_type: Type of transfer ('acquire', 'equip', 'store')
            
        Returns:
            Tuple[bool, str]: (Success, Message)
        """
        # Check LORE restrictions
        if item.get('is_lore', False):
            if not self.can_acquire_lore_item(character, item):
                return False, "You already have this LORE item."
                
        # Additional transfer validations could be added here
        
        return True, "Transfer allowed."

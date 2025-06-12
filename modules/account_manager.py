import json
import os
import logging
import hashlib
import time
from typing import Dict, Any, Tuple, Optional, List

class AccountManager:
    def __init__(self, accounts_file='accounts.json', characters_file='characters.json'):
        self.accounts_file = accounts_file
        self.characters_file = characters_file
        self.accounts = self._load_data(accounts_file)
        self.characters = self._load_data(characters_file)
        self.connected_clients = {}  # Dictionary to track connected clients
        self.last_tell_senders = {}  # Dictionary to track last tell sender per username
        self.NO_RENT_TIMEOUT = 300  # 5 minutes in seconds

    def _load_data(self, file_path):
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    logging.error(f"Error decoding JSON from {file_path}")
                    return {}
        return {}

    def _save_data(self, file_path, data):
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
            logging.info(f"Data saved to {file_path}.")
            return True
        except Exception as e:
            logging.error(f"Failed to save data to {file_path}: {e}")
            return False

    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def clean_no_rent_items(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove NO-RENT items from character if offline duration exceeds timeout.
        Returns cleaned character data.
        """
        try:
            current_time = time.time()
            last_logout = character.get('last_logout', 0)
            
            if current_time - last_logout > self.NO_RENT_TIMEOUT:
                # Track removed items for logging
                removed_items = []
                
                # Clean inventory
                original_inv = character.get('inventory', [])
                new_inv = []
                for item in original_inv:
                    if item.get('is_no_rent', False):
                        removed_items.append(item.get('name', 'Unknown Item'))
                    else:
                        new_inv.append(item)
                character['inventory'] = new_inv

                # Clean equipment
                equipment = character.get('equipment', {})
                for slot, item in equipment.items():
                    if item and item.get('is_no_rent', False):
                        removed_items.append(f"{item.get('name', 'Unknown Item')} from {slot}")
                        equipment[slot] = None

                # Clean containers in inventory
                for container in character.get('inventory', []):
                    if container.get('type') == 'containers':
                        original_contents = container.get('contents', [])
                        new_contents = []
                        for item in original_contents:
                            if item.get('is_no_rent', False):
                                removed_items.append(f"{item.get('name', 'Unknown Item')} from container")
                            else:
                                new_contents.append(item)
                        container['contents'] = new_contents

                if removed_items:
                    logging.info(f"NO-RENT items removed from {character['name']}: {', '.join(removed_items)}")

            return character

        except Exception as e:
            logging.error(f"Error cleaning NO-RENT items for character {character.get('name', 'Unknown')}: {e}")
            return character

    def username_exists(self, username):
        return username in self.accounts

    def validate_login(self, username, password):
        hashed_password = self._hash_password(password)
        if username in self.accounts and self.accounts[username]['password'] == hashed_password:
            return True
        return False

    def create_account(self, username, password):
        if username in self.accounts:
            return False, "Account already exists."
            
        hashed_password = self._hash_password(password)
        self.accounts[username] = {
            'password': hashed_password,
            'characters': [],
            'created_at': time.time()
        }
        
        if self._save_data(self.accounts_file, self.accounts):
            logging.info(f"Account '{username}' created successfully.")
            return True, "Account created successfully."
        else:
            logging.error(f"Failed to create account for '{username}'.")
            return False, "Failed to create account. Please try again."

    def get_characters(self, username):
        if username in self.accounts:
            characters = []
            for char_name in self.accounts[username]['characters']:
                if char_name in self.characters:
                    character = self.clean_no_rent_items(self.characters[char_name])
                    characters.append(character)
            return characters
        return []

    def create_character(self, username, character_name):
        if character_name in self.characters:
            logging.warning(f"Character '{character_name}' already exists.")
            return False, "Character already exists."
        
        new_character = {
            'name': character_name,
            'username': username,
            'created_at': time.time(),
            'last_login': None,
            'last_logout': None,
            'stats': {
                'HP': 20,
                'Max_HP': 20,
                'SP': 20,
                'Max_SP': 20,
                'AP': 0,
                'Max_AP': 0,
                'Strength': 5,
                'Tenacity': 5,
                'Agility': 5,
                'Intelligence': 5,
                'Revel': 5,
                'Defense': 0,
                'Ferocity': 3,
                'Resilience': 3,
                'Evasion': 3
            },
            'experience': 0,
            'level': 1,
            'equipment': {},
            'inventory': [],
            'room': '1',
            'in_combat': False
        }
        
        self.characters[character_name] = new_character
        self.accounts[username]['characters'].append(character_name)
        
        if self._save_data(self.characters_file, self.characters) and self._save_data(self.accounts_file, self.accounts):
            logging.info(f"Character '{character_name}' created for user '{username}'.")
            return True, "Character created successfully."
        else:
            logging.error(f"Failed to create character '{character_name}' for user '{username}'.")
            return False, "Failed to create character. Please try again."

    def get_character(self, username, character_name):
        if character_name in self.accounts.get(username, {}).get('characters', []):
            character = self.characters.get(character_name)
            if character:
                return self.clean_no_rent_items(character)
        return None

    def update_character(self, username, character):
        character_name = character['name']
        if character_name in self.accounts.get(username, {}).get('characters', []):
            self.characters[character_name] = character
            if self._save_data(self.characters_file, self.characters):
                logging.debug(f"Character '{character_name}' updated for user '{username}'.")
                return True
            else:
                logging.error(f"Failed to save character '{character_name}' for user '{username}'.")
                return False
        logging.error(f"Character '{character_name}' not found for user '{username}'.")
        return False

    def handle_character_logout(self, username: str, character: Dict[str, Any]) -> None:
        """Handle character logout, updating timestamps and cleaning up."""
        try:
            character['last_logout'] = time.time()
            self.update_character(username, character)
            logging.info(f"Character '{character['name']}' logout time recorded.")
        except Exception as e:
            logging.error(f"Error handling logout for character '{character.get('name', 'Unknown')}': {e}")

    def handle_character_login(self, username: str, character: Dict[str, Any]) -> Dict[str, Any]:
        """Handle character login, cleaning NO-RENT items and updating timestamps."""
        try:
            character = self.clean_no_rent_items(character)
            character['last_login'] = time.time()
            self.update_character(username, character)
            logging.info(f"Character '{character['name']}' login processed successfully.")
            return character
        except Exception as e:
            logging.error(f"Error handling login for character '{character.get('name', 'Unknown')}': {e}")
            return character

    def get_all_usernames(self):
        return list(self.accounts.keys())

    def get_all_characters(self):
        return list(self.characters.values())

    def select_character(self, username, client_socket):
        characters = self.get_characters(username)

        if not characters:
            client_socket.sendall(b"No characters found. Please create a new character.\n")
            client_socket.sendall(b"Enter a name for your new character: ")
            char_name = client_socket.recv(1024).decode().strip()

            if not char_name:
                client_socket.sendall(b"Character creation failed. Name cannot be empty.\n")
                return None

            success, message = self.create_character(username, char_name)
            if success:
                client_socket.sendall(f"Character '{char_name}' created successfully!\n".encode())
                return self.handle_character_login(username, self.characters[char_name])
            else:
                client_socket.sendall(f"Failed to create character: {message}\n".encode())
                return None

        client_socket.sendall(b"Select your character:\n")
        for index, char in enumerate(characters, start=1):
            client_socket.sendall(f"{index}. {char['name']}\n".encode())

        while True:
            client_socket.sendall(b"Enter the number of the character you wish to play: ")
            selection = client_socket.recv(1024).decode().strip()
            if selection.isdigit() and 1 <= int(selection) <= len(characters):
                selected_char = characters[int(selection) - 1]
                return self.handle_character_login(username, selected_char)
            else:
                client_socket.sendall(b"Invalid selection. Please try again.\n")

    def get_account_by_name(self, username):
        """Returns account information by username."""
        return self.accounts.get(username)

    def send_message_to_client(self, username, message):
        """Sends a message to the client socket associated with a username."""
        client_socket = self.connected_clients.get(username)
        if client_socket:
            try:
                client_socket.sendall(message.encode())
            except Exception as e:
                logging.error(f"Error sending message to {username}: {e}")
                return False
        else:
            logging.error(f"Client for {username} not found.")
            return False
        return True

    def broadcast_to_all_clients(self, message):
        for client_socket in self.connected_clients.values():
            try:
                client_socket.sendall(message.encode())
            except Exception as e:
                logging.error(f"Failed to send broadcast message to a client: {e}")

    def add_connected_client(self, username, client_socket):
        """Adds a connected client to the connected_clients dictionary."""
        self.connected_clients[username] = client_socket
        logging.info(f"Client for {username} added to connected clients.")

    def remove_connected_client(self, username):
        """Removes a client from the connected_clients dictionary when they disconnect."""
        if username in self.connected_clients:
            # Handle character logout if character exists
            for char_name in self.accounts.get(username, {}).get('characters', []):
                if char_name in self.characters:
                    self.handle_character_logout(username, self.characters[char_name])
                    
            del self.connected_clients[username]
            logging.info(f"Client for {username} removed from connected clients.")

    def is_connected(self, username):
        """Checks if the user is currently connected."""
        return username in self.connected_clients

    def set_last_tell_sender(self, recipient_username, sender_username):
        """Sets the last tell sender for a recipient."""
        self.last_tell_senders[recipient_username] = sender_username

    def get_last_tell_sender(self, recipient_username):
        """Gets the last tell sender for a recipient."""
        return self.last_tell_senders.get(recipient_username)

    def get_username_by_character_name(self, character_name):
        """Returns the username associated with a given character name."""
        for username, account in self.accounts.items():
            if character_name in account.get('characters', []):
                return username
        return None

    def get_character_name(self, username):
        """Returns the primary character name for a given username."""
        account = self.get_account_by_name(username)
        if account and account['characters']:
            return account['characters'][0]
        return "Unknown"

    def login_character(self, character_name):
        """Handle character login with NO-RENT processing."""
        character = self.characters.get(character_name)
        if character:
            username = character.get('username')
            if username:
                return self.handle_character_login(username, character)
        return None


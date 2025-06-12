# server.py

from modules.server_handler import GameServer, room_manager, mob_manager  # Import the existing managers

def start_server():
    """
    Starts the MUD server, accepting client connections.
    """
    print("STAIR MUD is now Online! Listening for connections on port 4000...")
    
    # Use the existing mob_manager
    game_server = GameServer(host='0.0.0.0', port=4000, mob_manager=mob_manager)
    game_server.start()

if __name__ == "__main__":
    start_server()
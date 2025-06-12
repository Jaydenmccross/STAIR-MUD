import json
import os

def fix_json_files(data_dir):
    # Read the rooms file
    with open(os.path.join(data_dir, 'rooms.json'), 'r') as f:
        rooms = json.load(f)
    
    # Read the items file
    with open(os.path.join(data_dir, 'items.json'), 'r') as f:
        items = json.load(f)

    # Create a set of all used VNUMs in rooms
    room_vnums = {str(room['vnum']) for room in rooms}

    # Create a set of all used VNUMs in standalone items
    item_vnums = {str(item['vnum']) for item in items}

    # Get the highest VNUM currently in use
    all_vnums = set()
    for vnum in room_vnums | item_vnums:
        try:
            all_vnums.add(int(vnum))
        except ValueError:
            pass
    
    next_vnum = max(all_vnums) + 1 if all_vnums else 1

    # Fix any duplicate VNUMs in items by assigning new ones
    fixed_items = []
    used_vnums = set()
    
    for item in items:
        current_vnum = str(item['vnum'])
        if current_vnum in used_vnums or current_vnum in room_vnums:
            # Assign a new VNUM
            while str(next_vnum) in room_vnums or str(next_vnum) in used_vnums:
                next_vnum += 1
            item['vnum'] = str(next_vnum)
            next_vnum += 1
        used_vnums.add(str(item['vnum']))
        fixed_items.append(item)

    # Save the fixed items back to the file
    with open(os.path.join(data_dir, 'items.json'), 'w') as f:
        json.dump(fixed_items, f, indent=4)

    print("Fixed items.json file. Room VNUMs:", sorted(list(room_vnums)))
    print("New item VNUMs:", sorted([str(item['vnum']) for item in fixed_items]))

if __name__ == "__main__":
    # Get the project directory (where your game_data folder is)
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_dir, 'game_data')
    
    print(f"Fixing files in: {data_dir}")
    fix_json_files(data_dir)
    print("Done!")
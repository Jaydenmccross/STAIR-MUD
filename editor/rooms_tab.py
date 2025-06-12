# In rooms_tab.py

import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
from base_tab import BaseTab

class RoomTab(BaseTab):
    def __init__(self, parent, file_paths, room_stats=None):
        # Define class attributes before calling parent's __init__
        self.directions = [
            "north", "south", "east", "west",
            "northeast", "northwest", "southeast", "southwest",
            "up", "down"
        ]
        self.exit_entries = {}
        self.TYPE_MAPPINGS = {
            "Room": "rooms"
        }
        super().__init__(parent, file_paths, room_stats or [])  # Pass empty list if room_stats is None
        self.setup_ui()
        
    def get_file_path(self):
        """Return the file path for room data."""
        return self.file_paths["Room"]

    def setup_ui(self):
        """Setup the room tab UI elements."""
        self.create_widgets()
        self.update_listbox()

    def create_widgets(self):
        """Create all widgets for the room tab."""
        # Basic Info Frame
        basic_frame = ttk.LabelFrame(self, text="Basic Information")
        basic_frame.grid(column=0, row=0, padx=5, pady=5, sticky="ew")

        # VNUM field
        ttk.Label(basic_frame, text="VNUM:").grid(column=0, row=0, padx=5, pady=5)
        self.vnum_entry = ttk.Entry(basic_frame, width=20)
        self.vnum_entry.grid(column=1, row=0, padx=5, pady=5)

        # Name field
        ttk.Label(basic_frame, text="Name:").grid(column=0, row=1, padx=5, pady=5)
        self.name_entry = ttk.Entry(basic_frame, width=50)
        self.name_entry.grid(column=1, row=1, padx=5, pady=5)

        # Description field
        ttk.Label(basic_frame, text="Description:").grid(column=0, row=2, padx=5, pady=5)
        self.desc_entry = tk.Text(basic_frame, height=4, width=50)
        self.desc_entry.grid(column=1, row=2, padx=5, pady=5)

        # Create notebook for different settings
        settings_notebook = ttk.Notebook(self)
        settings_notebook.grid(column=0, row=1, columnspan=2, padx=5, pady=5, sticky="nsew")

        # Add tabs to notebook
        exits_frame = self.create_exits_frame(settings_notebook)
        mobs_frame = self.create_mobs_frame(settings_notebook)
        items_frame = self.create_items_frame(settings_notebook)

        settings_notebook.add(exits_frame, text="Exits")
        settings_notebook.add(mobs_frame, text="Mobs")
        settings_notebook.add(items_frame, text="Items")

        # Save Button
        save_button = ttk.Button(self, text="Save Room", command=self.save_room)
        save_button.grid(column=0, row=2, columnspan=2, pady=10)

        # Room Listbox with Scrollbar
        self.listbox = tk.Listbox(self, height=10, width=50)
        self.listbox.grid(column=0, row=3, columnspan=2, padx=5, pady=5)
        self.listbox.bind("<Double-1>", self.on_select)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.listbox.yview)
        scrollbar.grid(column=2, row=3, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

    def create_exits_frame(self, parent):
        """Create the exits frame."""
        frame = ttk.LabelFrame(parent, text="Exits")
        frame.grid_columnconfigure(1, weight=1)

        # Create entries for each exit
        self.exit_entries = {}
        directions = ["North", "East", "South", "West", "Up", "Down"]
        for idx, direction in enumerate(directions):
            ttk.Label(frame, text=f"{direction}:").grid(column=0, row=idx, padx=5, pady=2)
            entry = ttk.Entry(frame, width=10)
            entry.grid(column=1, row=idx, padx=5, pady=2)
            self.exit_entries[direction] = entry

        return frame

    def create_mobs_frame(self, parent):
        """Create the enhanced mobs frame with respawn settings."""
        frame = ttk.LabelFrame(parent, text="Mobs")
        frame.grid_columnconfigure(1, weight=1)

        # Left side - Mob List
        list_frame = ttk.Frame(frame)
        list_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Mob Listbox with Scrollbar
        self.mob_listbox = tk.Listbox(list_frame, height=8, width=30)
        self.mob_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.mob_listbox.bind("<Double-1>", self.on_mob_select)
        self.mob_listbox.bind("<<ListboxSelect>>", self.on_mob_selection_change)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.mob_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.mob_listbox.configure(yscrollcommand=scrollbar.set)

        # Buttons frame
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=1, column=0, padx=5, pady=5)

        add_mob_btn = ttk.Button(button_frame, text="Add Mob", command=self.add_mob)
        add_mob_btn.pack(side=tk.LEFT, padx=2)

        remove_mob_btn = ttk.Button(button_frame, text="Remove Mob", command=self.remove_mob)
        remove_mob_btn.pack(side=tk.LEFT, padx=2)

        # Right side - Mob Settings
        settings_frame = ttk.LabelFrame(frame, text="Mob Settings")
        settings_frame.grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky="nsew")

        # Create mob settings entries
        ttk.Label(settings_frame, text="Initial Quantity:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.mob_quantity_entry = ttk.Entry(settings_frame, width=10)
        self.mob_quantity_entry.grid(row=0, column=1, padx=5, pady=2)
        self.mob_quantity_entry.insert(0, "1")

        ttk.Label(settings_frame, text="Max Instances:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.mob_max_instances_entry = ttk.Entry(settings_frame, width=10)
        self.mob_max_instances_entry.grid(row=1, column=1, padx=5, pady=2)
        self.mob_max_instances_entry.insert(0, "1")

        ttk.Label(settings_frame, text="Respawn Time (seconds):").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.mob_respawn_time_entry = ttk.Entry(settings_frame, width=10)
        self.mob_respawn_time_entry.grid(row=2, column=1, padx=5, pady=2)
        self.mob_respawn_time_entry.insert(0, "300")  # 5 minutes default

        # Mob Behavior Frame
        behavior_frame = ttk.LabelFrame(settings_frame, text="Behavior")
        behavior_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        self.mob_aggressive_var = tk.BooleanVar()
        ttk.Checkbutton(behavior_frame, text="Aggressive", variable=self.mob_aggressive_var).pack(pady=2)

        # Store mob settings for each mob name
        self.mob_settings = {}  # Will store settings per mob name

        return frame

    def create_items_frame(self, parent):
        """Create the items frame."""
        frame = ttk.LabelFrame(parent, text="Items")
        frame.grid_columnconfigure(1, weight=1)

        # Item Listbox with Scrollbar
        self.item_listbox = tk.Listbox(frame, height=5, width=30)
        self.item_listbox.grid(column=0, row=0, columnspan=2, padx=5, pady=5)
        self.item_listbox.bind("<Double-1>", self.on_item_select)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.item_listbox.yview)
        scrollbar.grid(column=2, row=0, sticky="ns")
        self.item_listbox.configure(yscrollcommand=scrollbar.set)

        # Add Item Button
        add_item_btn = ttk.Button(frame, text="Add Item", command=self.add_item)
        add_item_btn.grid(column=0, row=1, padx=5, pady=5)

        # Remove Item Button
        remove_item_btn = ttk.Button(frame, text="Remove Item", command=self.remove_item)
        remove_item_btn.grid(column=1, row=1, padx=5, pady=5)

        return frame

    def add_mob(self):
        """Add a mob to the room with settings."""
        dialog = self.MobSelectionDialog(self, "Add Mob", "Select Mob Name:")
        if dialog.result:
            mob_name = dialog.result.strip()
            if self.validate_mob_name(mob_name):
                # Don't add if already exists
                if mob_name in [self.mob_listbox.get(i) for i in range(self.mob_listbox.size())]:
                    messagebox.showerror("Error", f"Mob '{mob_name}' already added to room.")
                    return

                # Validate quantity field
                try:
                    quantity = int(self.mob_quantity_entry.get() or "1")  # Default to 1 if empty
                    max_instances = int(self.mob_max_instances_entry.get() or "1")  # Default to 1 if empty
                    respawn_time = int(self.mob_respawn_time_entry.get() or "300")  # Default to 300 if empty
                except ValueError:
                    messagebox.showerror("Error", "Quantity, max instances, and respawn time must be valid numbers.")
                    return

                # Add to listbox
                self.mob_listbox.insert(tk.END, mob_name)

                # Initialize settings for this mob
                self.mob_settings[mob_name] = {
                    'quantity': quantity,
                    'max_instances': max_instances,
                    'respawn_time': respawn_time,
                    'aggressive': self.mob_aggressive_var.get()
                }

    def remove_mob(self):
        """Remove a mob and its settings from the room."""
        selection = self.mob_listbox.curselection()
        if selection:
            mob_name = self.mob_listbox.get(selection[0])
            self.mob_listbox.delete(selection[0])
            # Remove settings for this mob
            if mob_name in self.mob_settings:
                del self.mob_settings[mob_name]

    def save_mob_settings(self):
        """Save current field values to settings for selected mob."""
        selection = self.mob_listbox.curselection()
        if not selection:
            return

        mob_name = self.mob_listbox.get(selection[0])
        try:
            # Validate numeric fields
            quantity = int(self.mob_quantity_entry.get())
            max_instances = int(self.mob_max_instances_entry.get())
            respawn_time = int(self.mob_respawn_time_entry.get())

            if quantity < 0 or max_instances < 0 or respawn_time < 0:
                raise ValueError("Values cannot be negative")

            if quantity > max_instances:
                raise ValueError("Initial quantity cannot exceed max instances")

            # Save settings
            self.mob_settings[mob_name] = {
                'quantity': quantity,
                'max_instances': max_instances,
                'respawn_time': respawn_time,
                'aggressive': self.mob_aggressive_var.get()
            }
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid numeric value: {str(e)}")

    def get_mob_vnum(self, mob_name):
        """Get mob VNUM from mobs.json file."""
        try:
            with open(self.file_paths["Mob"], 'r') as f:
                mobs = json.load(f)
                mob = next((m for m in mobs if m['name'] == mob_name), None)
                return str(mob['vnum']) if mob else None
        except Exception as e:
            logging.error(f"Error getting mob VNUM: {e}")
            return None

    def save_room(self):
        """Save the room data with enhanced mob handling."""
        try:
            # Validate basic fields
            vnum = self.vnum_entry.get().strip()
            if not vnum:
                messagebox.showerror("Error", "Please enter a VNUM.")
                return

            # Save current mob settings if a mob is selected
            self.save_mob_settings()

            # Build room data structure
            room_data = {
                "vnum": vnum,
                "name": self.name_entry.get().strip(),
                "description": self.desc_entry.get("1.0", "end-1c").strip(),
                "exits": {},
                "mobs": [],
                "items": [],
                "players": []  # Preserve existing players
            }

            # Process exits
            for direction, entry in self.exit_entries.items():
                exit_vnum = entry.get().strip()
                if exit_vnum:
                    room_data["exits"][direction.lower()] = exit_vnum

            # Load existing room data to preserve players
            existing_room = None
            try:
                with open(self.get_file_path(), 'r') as f:
                    rooms = json.load(f)
                    existing_room = next((room for room in rooms if str(room.get('vnum')) == str(vnum)), None)
            except Exception:
                rooms = []

            # Process mobs with new format
            for i in range(self.mob_listbox.size()):
                mob_name = self.mob_listbox.get(i)
                settings = self.mob_settings.get(mob_name, {})
                mob_vnum = self.get_mob_vnum(mob_name)
                
                if mob_vnum:
                    mob_template = {
                        "vnum": mob_vnum,
                        "name": mob_name,
                        "quantity": settings.get('quantity', 1),
                        "max_instances": settings.get('max_instances', 1),
                        "respawn_time": settings.get('respawn_time', 300),
                        "aggressive": settings.get('aggressive', False),
                        "is_template": True
                    }
                    room_data["mobs"].append(mob_template)

            # Process items (unchanged)
            try:
                with open(self.file_paths["Item"], 'r') as f:
                    items_data = json.load(f)
                    for i in range(self.item_listbox.size()):
                        item_name = self.item_listbox.get(i)
                        item_template = next((item for item in items_data if item['name'] == item_name), None)
                        if item_template:
                            item_data = item_template.copy()
                            room_data["items"].append(item_data)
            except Exception as e:
                logging.error(f"Error loading item data: {e}")

            # Preserve existing players if updating
            if existing_room and 'players' in existing_room:
                room_data['players'] = existing_room['players']

            # Update or add room
            found = False
            for i, room in enumerate(rooms):
                if str(room.get('vnum')) == str(vnum):
                    rooms[i] = room_data
                    found = True
                    break
            if not found:
                rooms.append(room_data)

            # Save to file
            with open(self.get_file_path(), 'w') as f:
                json.dump(rooms, f, indent=4)

            messagebox.showinfo("Success", f"Room '{room_data['name']}' saved successfully!")
            self.clear_fields()
            self.update_listbox()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save room: {str(e)}")
            logging.error(f"Error saving room: {str(e)}", exc_info=True)

    def on_select(self, event):
        """Enhanced room selection handler with mob settings."""
        selection = self.listbox.curselection()
        if not selection:
            return

        try:
            with open(self.get_file_path(), 'r') as f:
                rooms = json.load(f)
                
            selected_room = rooms[selection[0]]
            if not selected_room:
                raise ValueError("No room data found at selected index")
            
            # Clear current fields and settings
            self.clear_fields()
            self.mob_settings.clear()

            # Load basic info
            self.vnum_entry.insert(0, selected_room.get('vnum', ''))
            self.name_entry.insert(0, selected_room.get('name', ''))
            self.desc_entry.insert("1.0", selected_room.get('description', ''))

            # Load exits
            exits = selected_room.get('exits', {})
            for direction, vnum in exits.items():
                direction_key = direction.title()
                if direction_key in self.exit_entries:
                    self.exit_entries[direction_key].insert(0, str(vnum))

            # Load mobs with settings
            for mob in selected_room.get('mobs', []):
                if mob.get('is_template', False):  # Only load templates
                    mob_name = mob['name']
                    self.mob_listbox.insert(tk.END, mob_name)
                    self.mob_settings[mob_name] = {
                        'quantity': int(mob.get('quantity', 1)),
                        'max_instances': int(mob.get('max_instances', 1)),
                        'respawn_time': int(mob.get('respawn_time', 300)),
                        'aggressive': mob.get('aggressive', False)
                    }

            # Load items
            for item in selected_room.get('items', []):
                if isinstance(item, dict) and 'name' in item:
                    self.item_listbox.insert(tk.END, item['name'])

            # Select first mob if any exist and load its settings
            if self.mob_listbox.size() > 0:
                self.mob_listbox.select_set(0)
                self.on_mob_selection_change(None)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load room data: {str(e)}")
            logging.error(f"Error loading room: {str(e)}", exc_info=True)

    def update_listbox(self):
        """Update the room listbox with current rooms."""
        self.listbox.delete(0, tk.END)
        try:
            with open(self.file_paths["Room"], 'r') as f:
                rooms = json.load(f)
                for room in rooms:
                    display_text = f"VNUM: {room['vnum']} - Name: {room['name']}"
                    self.listbox.insert(tk.END, display_text)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def on_mob_select(self, event):
        """Handle mob selection from listbox."""
        selection = self.mob_listbox.curselection()
        if not selection:
            return

        mob_name = self.mob_listbox.get(selection[0])
        # Add logic to populate the fields with mob details
        # For example, you can load the mob details from the JSON file and populate the fields
        try:
            with open(self.file_paths["Mob"], 'r') as f:
                mobs = json.load(f)
                mob = next((mob for mob in mobs if mob['name'] == mob_name), None)
                if mob:
                    self.mob_quantity_entry.delete(0, "end")
                    self.mob_quantity_entry.insert(0, mob.get('quantity', ''))
                    self.mob_max_instances_entry.delete(0, "end")
                    self.mob_max_instances_entry.insert(0, mob.get('max_instances', ''))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load mob data: {str(e)}")
            logging.error(f"Error loading mob: {str(e)}", exc_info=True)

    def on_item_select(self, event):
        """Handle item selection from listbox."""
        selection = self.item_listbox.curselection()
        if not selection:
            return

        item_name = self.item_listbox.get(selection[0])
        # Add logic to populate the fields with item details
        # For example, you can load the item details from the JSON file and populate the fields
        try:
            with open(self.file_paths["Item"], 'r') as f:
                items = json.load(f)
                item = next((item for item in items if item['name'] == item_name), None)
                if item:
                    # Add logic to populate item fields if needed
                    pass
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load item data: {str(e)}")
            logging.error(f"Error loading item: {str(e)}", exc_info=True)

    def clear_fields(self):
        """Clear all input fields."""
        self.vnum_entry.delete(0, "end")
        self.name_entry.delete(0, "end")
        self.desc_entry.delete("1.0", "end")
        
        # Clear exit entries
        for entry in self.exit_entries.values():
            entry.delete(0, "end")
        
        # Clear mob listbox and quantity/max instances
        self.mob_listbox.delete(0, tk.END)
        self.mob_quantity_entry.delete(0, "end")
        self.mob_max_instances_entry.delete(0, "end")

        # Clear item listbox
        self.item_listbox.delete(0, tk.END)

    def validate_mob_name(self, mob_name):
        """Validate that a mob name exists."""
        try:
            with open(self.file_paths["Mob"], 'r') as f:
                mobs = json.load(f)
                if not any(mob.get('name') == mob_name for mob in mobs):
                    messagebox.showerror("Error", f"Mob with name {mob_name} does not exist.")
                    return False
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to validate mob name: {str(e)}")
            return False

    class MobSelectionDialog(tk.Toplevel):
        """Dialog for selecting a mob name."""
        def __init__(self, parent, title, prompt):
            super().__init__(parent)
            self.title(title)
            self.result = None
            
            self.transient(parent)
            self.grab_set()
            
            ttk.Label(self, text=prompt).pack(padx=5, pady=5)
            self.listbox = tk.Listbox(self, height=10, width=30)
            self.listbox.pack(padx=5, pady=5)
            self.listbox.bind("<Double-1>", self.on_select)

            scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.listbox.yview)
            scrollbar.pack(side="right", fill="y")
            self.listbox.configure(yscrollcommand=scrollbar.set)

            try:
                with open(parent.file_paths["Mob"], 'r') as f:
                    mobs = json.load(f)
                    for mob in mobs:
                        self.listbox.insert(tk.END, mob['name'])
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load mob data: {str(e)}")
                self.destroy()

            self.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
            self.listbox.focus_set()
            self.wait_window(self)

        def on_select(self, event):
            """Handle mob selection from listbox."""
            selection = self.listbox.curselection()
            if selection:
                self.result = self.listbox.get(selection[0])
                self.destroy()

    def add_item(self):
        """Add an item to the room."""
        dialog = self.ItemSelectionDialog(self, "Add Item", "Select Item Name:")
        if dialog.result:
            item_name = dialog.result.strip()
            if self.validate_item_name(item_name):
                self.item_listbox.insert(tk.END, item_name)

    def remove_item(self):
        """Remove an item from the room."""
        selection = self.item_listbox.curselection()
        if selection:
            self.item_listbox.delete(selection[0])

    def validate_item_name(self, item_name):
        """Validate that an item name exists."""
        try:
            with open(self.file_paths["Item"], 'r') as f:
                items = json.load(f)
                if not any(item.get('name') == item_name for item in items):
                    messagebox.showerror("Error", f"Item with name {item_name} does not exist.")
                    return False
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to validate item name: {str(e)}")
            return False

    class ItemSelectionDialog(tk.Toplevel):
        """Dialog for selecting an item name."""
        def __init__(self, parent, title, prompt):
            super().__init__(parent)
            self.title(title)
            self.result = None
            
            self.transient(parent)
            self.grab_set()
            
            ttk.Label(self, text=prompt).pack(padx=5, pady=5)
            self.listbox = tk.Listbox(self, height=10, width=30)
            self.listbox.pack(padx=5, pady=5)
            self.listbox.bind("<Double-1>", self.on_select)

            scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.listbox.yview)
            scrollbar.pack(side="right", fill="y")
            self.listbox.configure(yscrollcommand=scrollbar.set)

            try:
                with open(parent.file_paths["Item"], 'r') as f:
                    items = json.load(f)
                    for item in items:
                        self.listbox.insert(tk.END, item['name'])
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load item data: {str(e)}")
                self.destroy()

            self.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
            self.listbox.focus_set()
            self.wait_window(self)

        def on_select(self, event):
            """Handle item selection from listbox."""
            selection = self.listbox.curselection()
            if selection:
                self.result = self.listbox.get(selection[0])
                self.destroy()

    def on_mob_selection_change(self, event):
        """Handle mob selection changes."""
        selection = self.mob_listbox.curselection()
        if not selection:
            return

        mob_name = self.mob_listbox.get(selection[0])
        settings = self.mob_settings.get(mob_name, {})

        # Update settings fields with stored values
        self.mob_quantity_entry.delete(0, tk.END)
        self.mob_quantity_entry.insert(0, str(settings.get('quantity', 1)))

        self.mob_max_instances_entry.delete(0, tk.END)
        self.mob_max_instances_entry.insert(0, str(settings.get('max_instances', 1)))

        self.mob_respawn_time_entry.delete(0, tk.END)
        self.mob_respawn_time_entry.insert(0, str(settings.get('respawn_time', 300)))

        self.mob_aggressive_var.set(settings.get('aggressive', False))
import tkinter as tk
from tkinter import ttk, messagebox
import json
from base_tab import BaseTab

class ContainerTab(BaseTab):
    def __init__(self, parent, file_paths, stats=None):
        self.container_types = ["Bag", "Chest"]
        self.TYPE_MAPPINGS = {
            "Container": "containers"
        }
        super().__init__(parent, file_paths, stats or [])

    def get_file_path(self):
        """Return the file path for containers data."""
        return self.file_paths["Container"]

    def setup_ui(self):
        """Setup the container tab UI elements."""
        # Basic Information Frame
        basic_frame = ttk.LabelFrame(self, text="Basic Information")
        basic_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        
        self.container_vnum_entry = self.create_labeled_entry(basic_frame, "VNUM:", 0, width=20)
        self.container_name_entry = self.create_labeled_entry(basic_frame, "Name:", 1, width=50)
        self.container_short_desc_entry = self.create_labeled_entry(basic_frame, "Short Description:", 2, width=50)
        self.container_long_desc_entry = self.create_labeled_text(basic_frame, "Long Description:", 3, height=4, width=50)

        # Container Properties Frame
        properties_frame = ttk.LabelFrame(self, text="Container Properties")
        properties_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        # Container Type Selection
        ttk.Label(properties_frame, text="Container Type:").grid(column=0, row=0, padx=5, pady=5, sticky="W")
        self.container_type_var = tk.StringVar(value=self.container_types[0])
        self.container_type_menu = ttk.OptionMenu(
            properties_frame,
            self.container_type_var,
            self.container_types[0],
            *self.container_types
        )
        self.container_type_menu.grid(column=1, row=0, padx=5, pady=5, sticky="W")

        # Capacity Frame
        limits_frame = ttk.LabelFrame(properties_frame, text="Container Properties")
        limits_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        self.capacity_entry = self.create_labeled_entry(limits_frame, "Capacity (Items):", 0, width=10)
        
        # Key Name Frame (for lockable containers)
        key_frame = ttk.LabelFrame(properties_frame, text="Key Properties")
        key_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        
        self.key_name_entry = self.create_labeled_entry(key_frame, "Key Name:", 0, width=30)
        ttk.Label(key_frame, text="(Leave empty if no key required)").grid(row=1, column=0, columnspan=2, padx=5, pady=2)

        # Container Flags Frame
        flags_frame = ttk.LabelFrame(self, text="Container Flags")
        flags_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.create_flags_section(flags_frame)

        # Value Frame
        value_frame = ttk.LabelFrame(self, text="Item Properties")
        value_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.container_value_entry = self.create_labeled_entry(value_frame, "Value (Gold):", 0, width=20)

        # Buttons frame
        button_frame = ttk.Frame(self)
        button_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=5)

        # Reset Button
        self.create_reset_button(button_frame, 0)

        # Save Button
        save_button = ttk.Button(button_frame, text="Save Container", command=self.save_container)
        save_button.grid(column=1, row=0, padx=5, pady=5)

        # Container Listbox
        self.setup_listbox()

    def create_flags_section(self, parent):
        """Create the container flags section with automatic Closeable setting."""
        self.flag_vars = {}
        flags = {
            "Closeable": "Container can be opened and closed",
            "Pickproof": "Cannot be picked open by lockpicking skills",
            "Locked": "Container starts in a locked state",
            "Key_Required": "Requires a specific key to unlock",
            "Immobile": "Cannot be picked up once placed",
            "No_Steal": "Cannot be stolen by players or NPCs"
        }
        
        for i, (flag, tooltip) in enumerate(flags.items()):
            var = tk.BooleanVar()
            self.flag_vars[flag] = var
            checkbox = ttk.Checkbutton(
                parent,
                text=flag,
                variable=var,
                command=lambda f=flag: self.handle_flag_change(f) if f in ["Key_Required"] else None
            )
            checkbox.grid(row=i//3, column=i%3, padx=15, pady=5, sticky="w")

    def handle_flag_change(self, flag):
        """Handle flag checkbox changes."""
        if flag == "Key_Required" and self.flag_vars["Key_Required"].get():
            # If Key_Required is checked, automatically check Closeable
            self.flag_vars["Closeable"].set(True)

    def save_container(self):
        """Save container data with validation."""
        # Validate required fields
        vnum = self.container_vnum_entry.get().strip()
        if not self.check_vnum(vnum):
            return

        container_name = self.container_name_entry.get().strip()
        if not container_name:
            messagebox.showerror("Error", "Please enter a container name.")
            return

        # Validate numeric fields
        try:
            capacity = int(self.capacity_entry.get().strip() or "0")
            value = int(self.container_value_entry.get().strip() or "0")
        except ValueError:
            messagebox.showerror("Error", "Capacity and value must be numeric.")
            return

        # Collect flags
        flags = {flag: var.get() for flag, var in self.flag_vars.items()}

        # Validate key requirements
        if flags.get("Key_Required") and not self.key_name_entry.get().strip():
            messagebox.showerror("Error", "Key name is required when Key_Required is checked.")
            return

        # Ensure Closeable is set if Key_Required is checked
        if flags.get("Key_Required"):
            flags["Closeable"] = True

        # Create container data
        container_data = {
            "vnum": vnum,
            "name": container_name,
            "type": "containers",
            "container_type": self.container_type_var.get(),
            "short_desc": self.container_short_desc_entry.get().strip(),
            "long_desc": self.container_long_desc_entry.get("1.0", tk.END).strip(),
            "capacity": capacity,
            "key_name": self.key_name_entry.get().strip(),
            "flags": flags,
            "value": value
        }

        if self.save_to_json(container_data):
            messagebox.showinfo("Success", "Container saved successfully!")
            self.reset_fields()
            self.refresh_listbox()

    def clear_fields(self):
        """Clear all input fields."""
        self.container_vnum_entry.delete(0, tk.END)
        self.container_name_entry.delete(0, tk.END)
        self.container_short_desc_entry.delete(0, tk.END)
        self.container_long_desc_entry.delete("1.0", tk.END)
        self.capacity_entry.delete(0, tk.END)
        self.key_name_entry.delete(0, tk.END)
        self.container_value_entry.delete(0, tk.END)
        self.container_type_var.set(self.container_types[0])
        
        # Reset all flags
        for var in self.flag_vars.values():
            var.set(False)

    def setup_listbox(self):
        """Setup the listbox for displaying existing containers with edit functionality."""
        listbox_frame = ttk.LabelFrame(self, text="Existing Containers")
        listbox_frame.grid(row=0, column=2, rowspan=5, padx=5, pady=5, sticky="nsew")
        
        self.listbox = tk.Listbox(listbox_frame, width=40, height=30)
        self.listbox.pack(padx=5, pady=5, fill="both", expand=True)
        
        # Bind double-click and Return key to edit function
        self.listbox.bind('<Double-Button-1>', self.edit_selected)
        self.listbox.bind('<Return>', self.edit_selected)
        
        self.refresh_listbox()

    def refresh_listbox(self):
        """Refresh the listbox with current container data."""
        self.listbox.delete(0, tk.END)
        try:
            with open(self.get_file_path(), 'r') as f:
                containers = json.load(f)
                for container in containers:
                    self.listbox.insert(tk.END, f"{container['vnum']}: {container['name']}")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def edit_selected(self, event=None):
        """Load the selected container for editing."""
        if not self.listbox.curselection():
            return
            
        selection = self.listbox.get(self.listbox.curselection())
        vnum = selection.split(':')[0].strip()
        
        try:
            with open(self.get_file_path(), 'r') as f:
                containers = json.load(f)
                container = next((c for c in containers if str(c['vnum']) == vnum), None)
                
                if container:
                    # Store the current VNUM being edited
                    self.current_edit_vnum = vnum
                    
                    # Clear current fields
                    self.clear_fields()
                    
                    # Fill in the fields with container data
                    self.container_vnum_entry.insert(0, container['vnum'])
                    self.container_name_entry.insert(0, container['name'])
                    self.container_short_desc_entry.insert(0, container.get('short_desc', ''))
                    self.container_long_desc_entry.insert("1.0", container.get('long_desc', ''))
                    self.capacity_entry.insert(0, str(container.get('capacity', 0)))
                    self.key_name_entry.insert(0, container.get('key_name', ''))
                    self.container_value_entry.insert(0, str(container.get('value', 0)))
                    
                    # Set container type
                    if container.get('container_type') in self.container_types:
                        self.container_type_var.set(container['container_type'])
                    
                    # Set flags
                    flags = container.get('flags', {})
                    for flag, var in self.flag_vars.items():
                        var.set(flags.get(flag, False))
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error loading container data: {str(e)}")
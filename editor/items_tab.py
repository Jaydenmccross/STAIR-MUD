import tkinter as tk
from tkinter import ttk, messagebox
import json
from base_tab import BaseTab

class ItemTab(BaseTab):
    def __init__(self, parent, file_paths, stats):
        self.TYPE_MAPPINGS = {
            "Item": "items"
        }
        super().__init__(parent, file_paths, stats)

    def get_file_path(self):
        """Get the file path for items."""
        return self.file_paths["Item"]

    def setup_ui(self):
        """Setup the item tab UI elements."""
        # Basic Information Frame
        basic_frame = ttk.LabelFrame(self, text="Basic Information")
        basic_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        
        self.item_vnum_entry = self.create_labeled_entry(basic_frame, "VNUM:", 0, width=20)
        self.item_name_entry = self.create_labeled_entry(basic_frame, "Name:", 1, width=50)
        self.item_short_desc_entry = self.create_labeled_entry(basic_frame, "Short Description:", 2, width=50)
        self.item_long_desc_entry = self.create_labeled_text(basic_frame, "Long Description:", 3, height=4, width=50)

        # Item Properties Frame
        properties_frame = ttk.LabelFrame(self, text="Item Properties")
        properties_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        # Value Entry
        self.item_value_entry = self.create_labeled_entry(properties_frame, "Value (Gold):", 0, width=20)

        # Flags Frame
        flags_frame = ttk.LabelFrame(self, text="Item Flags")
        flags_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        # Create a frame for basic item flags
        basic_flags_frame = ttk.Frame(flags_frame)
        basic_flags_frame.pack(fill="x", padx=5, pady=5)

        # Item Flags
        self.immobile_var = tk.BooleanVar()
        self.readable_var = tk.BooleanVar()
        self.no_take_var = tk.BooleanVar()

        ttk.Checkbutton(basic_flags_frame, text="Immobile", variable=self.immobile_var).grid(row=0, column=0, padx=5, pady=5)
        ttk.Checkbutton(basic_flags_frame, text="Readable", variable=self.readable_var, command=self.toggle_read_text).grid(row=0, column=1, padx=5, pady=5)
        ttk.Checkbutton(basic_flags_frame, text="No Take", variable=self.no_take_var).grid(row=0, column=2, padx=5, pady=5)

        # LORE and NO-RENT flags
        special_flags_frame = ttk.Frame(flags_frame)
        special_flags_frame.pack(fill="x", padx=5, pady=5)

        ttk.Checkbutton(
            special_flags_frame,
            text="LORE (Limit One Per Character)",
            variable=self.is_lore_var
        ).grid(row=0, column=0, padx=5, pady=5, sticky="w")

        ttk.Checkbutton(
            special_flags_frame,
            text="NO-RENT (Removed After Logout)",
            variable=self.is_no_rent_var
        ).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Read Text Frame (initially hidden)
        self.read_text_frame = ttk.LabelFrame(self, text="Read Text")
        self.read_text_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.read_text_entry = tk.Text(self.read_text_frame, height=4, width=50)
        self.read_text_entry.pack(padx=5, pady=5, fill="both", expand=True)
        self.toggle_read_text()  # Initially hide the read text frame

        # Buttons frame
        button_frame = ttk.Frame(self)
        button_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=5)

        # Reset Button
        self.create_reset_button(button_frame, 0).grid(column=0, row=0, padx=5, pady=5)

        # Save Button
        save_button = ttk.Button(button_frame, text="Save Item", command=self.save_item)
        save_button.grid(column=1, row=0, padx=5, pady=5)

        # Item Listbox with Scrollbar
        listbox_frame = ttk.Frame(self)
        listbox_frame.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.item_listbox = tk.Listbox(listbox_frame, height=10, width=50, yscrollcommand=scrollbar.set)
        self.item_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.item_listbox.yview)
        
        self.item_listbox.bind("<Double-1>", self.edit_item)
        self.update_item_listbox()

    def toggle_read_text(self):
        """Show/hide read text based on readable checkbox."""
        if self.readable_var.get():
            self.read_text_frame.grid()
        else:
            self.read_text_frame.grid_remove()

    def save_item(self):
        """Save item data with validation."""
        # Validate required fields
        vnum = self.item_vnum_entry.get().strip()
        if not self.check_vnum(vnum):
            return

        item_name = self.item_name_entry.get().strip()
        if not item_name:
            messagebox.showerror("Error", "Please enter an item name.")
            return

        # Validate numeric field
        try:
            value = int(self.item_value_entry.get().strip() or "0")
        except ValueError:
            messagebox.showerror("Error", "Value must be an integer.")
            return

        # Validate readable flag and text
        if self.readable_var.get() and not self.read_text_entry.get("1.0", "end-1c").strip():
            messagebox.showerror("Error", "Readable items must have read text.")
            return

        # Create item data
        item_data = {
            "vnum": vnum,
            "name": item_name,
            "type": "items",
            "short_desc": self.item_short_desc_entry.get().strip(),
            "long_desc": self.item_long_desc_entry.get("1.0", "end-1c").strip(),
            "value": value,
            "immobile": self.immobile_var.get(),
            "readable": self.readable_var.get(),
            "no_take": self.no_take_var.get(),
            "is_lore": self.is_lore_var.get(),
            "is_no_rent": self.is_no_rent_var.get()
        }

        # Add read text if item is readable
        if self.readable_var.get():
            item_data["read_text"] = self.read_text_entry.get("1.0", "end-1c").strip()

        # Save the data
        if self.save_to_json(item_data):
            messagebox.showinfo("Success", "Item saved successfully!")
            self.clear_fields()
            self.update_item_listbox()

    def clear_fields(self):
        """Clear all input fields."""
        self.item_vnum_entry.delete(0, "end")
        self.item_name_entry.delete(0, "end")
        self.item_short_desc_entry.delete(0, "end")
        self.item_long_desc_entry.delete("1.0", "end")
        self.item_value_entry.delete(0, "end")
        self.read_text_entry.delete("1.0", "end")
        
        # Reset checkboxes
        self.immobile_var.set(False)
        self.readable_var.set(False)
        self.no_take_var.set(False)
        self.is_lore_var.set(False)
        self.is_no_rent_var.set(False)
        
        # Update read text visibility
        self.toggle_read_text()

    def update_item_listbox(self):
        """Update the item listbox with current items."""
        self.item_listbox.delete(0, tk.END)
        try:
            with open(self.get_file_path(), 'r') as f:
                try:
                    items = json.load(f)
                    if not isinstance(items, list):
                        items = []
                    for item in items:
                        display_text = f"VNUM: {item['vnum']} - Name: {item['name']}"
                        self.item_listbox.insert(tk.END, display_text)
                except json.JSONDecodeError:
                    messagebox.showerror("Error", "Failed to parse items file.")
        except FileNotFoundError:
            messagebox.showerror("Error", "Items file not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Error updating item list: {str(e)}")

    def edit_item(self, event):
        """Load selected item for editing."""
        selected = self.item_listbox.curselection()
        if not selected:
            return

        try:
            with open(self.get_file_path(), "r") as f:
                items = json.load(f)
                if not isinstance(items, list):
                    items = []
                item = items[selected[0]]
                
                # Set current edit vnum
                self.current_edit_vnum = str(item["vnum"])
                
                # Load basic fields
                self.item_vnum_entry.delete(0, "end")
                self.item_vnum_entry.insert(0, item["vnum"])
                self.item_name_entry.delete(0, "end")
                self.item_name_entry.insert(0, item["name"])
                self.item_short_desc_entry.delete(0, "end")
                self.item_short_desc_entry.insert(0, item["short_desc"])
                self.item_long_desc_entry.delete("1.0", "end")
                self.item_long_desc_entry.insert("1.0", item["long_desc"])
                
                # Load value
                self.item_value_entry.delete(0, "end")
                self.item_value_entry.insert(0, item.get("value", "0"))
                
                # Load flags
                self.immobile_var.set(item.get("immobile", False))
                self.readable_var.set(item.get("readable", False))
                self.no_take_var.set(item.get("no_take", False))
                self.is_lore_var.set(item.get("is_lore", False))
                self.is_no_rent_var.set(item.get("is_no_rent", False))
                
                # Load read text if present
                self.read_text_entry.delete("1.0", "end")
                if "read_text" in item:
                    self.read_text_entry.insert("1.0", item["read_text"])
                
                # Update read text visibility
                self.toggle_read_text()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load item: {str(e)}")
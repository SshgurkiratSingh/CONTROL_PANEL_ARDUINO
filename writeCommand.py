import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import threading
import time
from flask import Flask, request, jsonify

# Global variable to hold the GUI instance for API access.
gui_instance = None


class SerialReader(threading.Thread):
    def __init__(self, ser, app):
        super().__init__()
        self.ser = ser
        self.app = app  # reference to the main GUI app (to update UI)
        self.running = True
        self.daemon = True  # exit when main program closes

    def run(self):
        while self.running:
            if self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        self.app.process_serial_line(line)
                except Exception as e:
                    self.app.log_message(f"Serial read error: {e}")
            time.sleep(0.1)

    def stop(self):
        self.running = False


class ArduinoGUI(tk.Tk):
    def __init__(self, serial_port, baud_rate):
        super().__init__()
        self.title("Arduino Parameter Control GUI")
        self.geometry("900x700")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Instance variable to store parameters.
        # Keys are parameter names; values are dicts with keys: index, min, max, current.
        self.parameters = {}

        # Open serial connection.
        try:
            self.ser = serial.Serial(serial_port, baud_rate, timeout=1)
        except Exception as e:
            messagebox.showerror("Serial Connection Error",
                                 f"Could not open {serial_port}: {e}")
            self.destroy()
            return

        # Allow Arduino to reset.
        time.sleep(2)

        # Initialize software name variable.
        self.software_name = "Unknown"

        # Create UI elements.
        self.create_widgets()

        # Start serial reader thread.
        self.serial_reader = SerialReader(self.ser, self)
        self.serial_reader.start()

    def create_widgets(self):
        # Top frame: Connection Status
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill=tk.X)
        self.connection_label = ttk.Label(
            top_frame, text=f"Connected to {self.ser.port} at {self.ser.baudrate}")
        self.connection_label.pack(side=tk.LEFT)

        # Dedicated bar for reading pins.
        read_pin_frame = ttk.Frame(self, padding=(10, 5))
        read_pin_frame.pack(fill=tk.X)
        ttk.Label(read_pin_frame, text="Pin Type:").grid(
            row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.pin_type = tk.StringVar(value="Digital")
        digital_rb = ttk.Radiobutton(
            read_pin_frame, text="Digital", variable=self.pin_type, value="Digital", command=self.update_pin_options)
        analog_rb = ttk.Radiobutton(
            read_pin_frame, text="Analog", variable=self.pin_type, value="Analog", command=self.update_pin_options)
        digital_rb.grid(row=0, column=1, padx=5, pady=5)
        analog_rb.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(read_pin_frame, text="Select Pin:").grid(
            row=0, column=3, padx=5, pady=5, sticky=tk.W)
        self.pin_select = ttk.Combobox(read_pin_frame, state="readonly")
        self.pin_select.grid(row=0, column=4, padx=5, pady=5)
        self.update_pin_options()  # Populate with default (Digital) options

        read_btn = ttk.Button(
            read_pin_frame, text="Read Pin", command=self.read_pin)
        read_btn.grid(row=0, column=5, padx=5, pady=5)

        ttk.Label(read_pin_frame, text="Reading Result:").grid(
            row=0, column=6, padx=5, pady=5, sticky=tk.W)
        self.pin_result_label = ttk.Label(read_pin_frame, text="N/A")
        self.pin_result_label.grid(row=0, column=7, padx=5, pady=5)

        # Main PanedWindow: Left for parameters, right for tabs.
        main_pane = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left Frame: Parameter List inside a labeled frame.
        left_frame = ttk.Labelframe(
            main_pane, text="Parameters", padding=10, width=300)
        left_frame.pack_propagate(False)
        self.tree = ttk.Treeview(left_frame, columns=(
            "Index", "Name", "Min", "Max", "Current"), show="headings")
        for col, width in zip(("Index", "Name", "Min", "Max", "Current"), (50, 100, 60, 60, 60)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        clear_params_btn = ttk.Button(
            left_frame, text="Clear Parameter List", command=self.clear_parameters)
        clear_params_btn.pack(pady=5)
        main_pane.add(left_frame, weight=1)

        # Right Frame: Notebook for various tabs.
        right_frame = ttk.Frame(main_pane, padding=10)
        main_pane.add(right_frame, weight=3)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Add Parameter
        add_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(add_tab, text="Add Parameter")
        ttk.Label(add_tab, text="Name:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.add_name = ttk.Entry(add_tab)
        self.add_name.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(add_tab, text="Min:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.add_min = ttk.Entry(add_tab)
        self.add_min.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(add_tab, text="Max:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.add_max = ttk.Entry(add_tab)
        self.add_max.grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(add_tab, text="Current:").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.add_current = ttk.Entry(add_tab)
        self.add_current.grid(row=3, column=1, padx=5, pady=5)
        add_btn = ttk.Button(add_tab, text="Add Parameter",
                             command=self.add_parameter)
        add_btn.grid(row=4, column=0, columnspan=2, pady=10)

        # Tab 2: Update Parameter
        update_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(update_tab, text="Update Parameter")
        ttk.Label(update_tab, text="Name:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.update_name = ttk.Entry(update_tab)
        self.update_name.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(update_tab, text="New Value:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.update_value = ttk.Entry(update_tab)
        self.update_value.grid(row=1, column=1, padx=5, pady=5)
        update_btn = ttk.Button(
            update_tab, text="Update Value", command=self.update_parameter)
        update_btn.grid(row=2, column=0, columnspan=2, pady=10)

        # Tab 3: Get Parameter
        get_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(get_tab, text="Get Parameter")
        ttk.Label(get_tab, text="Name:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.get_name = ttk.Entry(get_tab)
        self.get_name.grid(row=0, column=1, padx=5, pady=5)
        get_btn = ttk.Button(
            get_tab, text="Get Current Value", command=self.get_parameter)
        get_btn.grid(row=1, column=0, columnspan=2, pady=10)

        # Tab 4: Manual Command
        manual_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(manual_tab, text="Manual Command")
        ttk.Label(manual_tab, text="Command:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.manual_cmd = ttk.Entry(manual_tab, width=40)
        self.manual_cmd.grid(row=0, column=1, padx=5, pady=5)
        manual_btn = ttk.Button(manual_tab, text="Send",
                                command=self.send_manual_command)
        manual_btn.grid(row=1, column=0, columnspan=2, pady=10)
        refresh_btn = ttk.Button(
            manual_tab, text="Refresh Parameter List", command=self.refresh_parameters)
        refresh_btn.grid(row=2, column=0, columnspan=2, pady=10)

        # Tab 5: Software Settings
        software_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(software_tab, text="Software")
        ttk.Label(software_tab, text="Software Name:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.software_entry = ttk.Entry(software_tab)
        self.software_entry.grid(row=0, column=1, padx=5, pady=5)
        set_software_btn = ttk.Button(
            software_tab, text="Set Software", command=self.set_software)
        set_software_btn.grid(row=1, column=0, columnspan=2, pady=10)
        ttk.Label(software_tab, text="Current Software Name:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.current_software_label = ttk.Label(
            software_tab, text=self.software_name)
        self.current_software_label.grid(row=2, column=1, padx=5, pady=5)

        # Bottom Frame: Log Window in a labeled frame.
        log_frame = ttk.Labelframe(self, text="Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        clear_log_btn = ttk.Button(
            log_frame, text="Clear Log", command=self.clear_log)
        clear_log_btn.pack(pady=5)

    def update_pin_options(self):
        """Update the combobox values based on selected pin type."""
        if self.pin_type.get() == "Digital":
            # For Arduino Uno, digital pins (excluding 0 and 1 used for Serial) can be 2-13.
            self.pin_select['values'] = [str(i) for i in range(2, 14)]
            self.pin_select.current(0)
        else:
            # For analog, show A0-A5.
            self.pin_select['values'] = [f"A{i}" for i in range(6)]
            self.pin_select.current(0)

    def read_pin(self):
        pin_type = self.pin_type.get()
        pin_value = self.pin_select.get().strip()
        if pin_type == "Digital":
            # Send command: read:digital,<pin>
            cmd = f"read:digital,{pin_value}"
        else:
            # For analog, convert "A0" -> index 0, etc.
            try:
                index = int(pin_value[1:])
            except Exception as e:
                self.log_message("Invalid analog pin selection.")
                return
            cmd = f"read:analog,{index}"
        self.send_command(cmd)

    def add_parameter(self):
        name = self.add_name.get().strip()
        min_val = self.add_min.get().strip()
        max_val = self.add_max.get().strip()
        cur_val = self.add_current.get().strip()
        if not name or not min_val or not max_val or not cur_val:
            self.log_message("All fields are required for adding a parameter.")
            return
        cmd = f"add:param,{name},{min_val},{max_val},{cur_val}"
        self.send_command(cmd)

    def update_parameter(self):
        name = self.update_name.get().strip()
        new_val = self.update_value.get().strip()
        if not name or not new_val:
            self.log_message("Name and new value are required for update.")
            return
        cmd = f"update:paramsCurval,{name},{new_val}"
        self.send_command(cmd)

    def get_parameter(self):
        name = self.get_name.get().strip()
        if not name:
            self.log_message("Please enter a parameter name.")
            return
        cmd = f"get:paramCurval,{name}"
        self.send_command(cmd)

    def send_manual_command(self):
        cmd = self.manual_cmd.get().strip()
        if not cmd:
            self.log_message("Please enter a command.")
            return
        self.send_command(cmd)

    def refresh_parameters(self):
        self.send_command("get:AlladdedParams")

    def set_software(self):
        name = self.software_entry.get().strip()
        if not name:
            self.log_message("Please enter a software name.")
            return
        cmd = f"set:software,{name}"
        self.send_command(cmd)

    def send_command(self, cmd):
        self.log_message("Sending: " + cmd)
        try:
            self.ser.write((cmd + "\n").encode("utf-8"))
        except Exception as e:
            self.log_message("Error sending command: " + str(e))

    def thread_safe_send_command(self, cmd):
        """Schedule a command to be sent from the Tkinter main thread."""
        self.after(0, lambda: self.send_command(cmd))

    def process_serial_line(self, line):
        """Parse a CSV message from Arduino and update UI and parameter store."""
        self.log_message("Received: " + line)
        parts = line.split(',')
        if not parts:
            return

        prefix = parts[0]
        # Check for digital read result: D,<pin>,<value>
        if prefix == "D" and len(parts) == 3 and parts[1].strip().isdigit():
            pin = parts[1].strip()
            value = parts[2].strip()
            self.pin_result_label.config(text=f"Digital Pin {pin}: {value}")
        # Check for analog read result: A,<index>,<value>
        elif prefix == "A" and len(parts) == 3 and parts[1].strip().isdigit():
            index = parts[1].strip()
            value = parts[2].strip()
            self.pin_result_label.config(text=f"Analog Pin A{index}: {value}")
        # Parameter addition message.
        elif prefix == "A":
            if len(parts) >= 2:
                name = parts[1]
                self.parameters[name] = {
                    "index": None, "min": None, "max": None, "current": None}
                self.log_message(f"Parameter added: {name}")
        elif prefix == "U" and len(parts) >= 3:
            name = parts[1]
            new_val = parts[2]
            if name in self.parameters:
                self.parameters[name]["current"] = new_val
            else:
                self.parameters[name] = {
                    "index": None, "min": None, "max": None, "current": new_val}
            self.log_message(f"Parameter {name} updated to {new_val}")
        elif prefix == "S":
            if len(parts) == 3 and parts[1].strip().lower() == "software set to":
                self.software_name = parts[2].strip()
                self.current_software_label.config(text=self.software_name)
                self.log_message(
                    f"Software name updated to: {self.software_name}")
            elif len(parts) >= 4:
                index = parts[1]
                name = parts[2]
                current = parts[3]
                self.parameters[name] = {
                    "index": index, "min": None, "max": None, "current": current}
                self.log_message(
                    f"Switched to parameter {name} (index {index})")
        elif prefix == "G" and len(parts) >= 3:
            name = parts[1]
            value = parts[2]
            self.parameters[name] = {"index": None,
                                     "min": None, "max": None, "current": value}
            self.log_message(f"Parameter {name} current value: {value}")
        elif prefix == "L" and len(parts) >= 6:
            index = parts[1]
            name = parts[2]
            min_val = parts[3]
            max_val = parts[4]
            current = parts[5]
            self.parameters[name] = {
                "index": index, "min": min_val, "max": max_val, "current": current}
            self.log_message(
                f"List: {name} -> min:{min_val}, max:{max_val}, current:{current}")
        else:
            self.log_message("Unrecognized message: " + line)
        self.update_parameter_list()

    def update_parameter_list(self):
        """Clear and repopulate the Treeview with current parameter data and adjust its height."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for name, info in self.parameters.items():
            idx = info.get("index") if info.get("index") is not None else "-"
            min_val = info.get("min") if info.get("min") is not None else "-"
            max_val = info.get("max") if info.get("max") is not None else "-"
            curr = info.get("current") if info.get(
                "current") is not None else "-"
            self.tree.insert("", tk.END, values=(
                idx, name, min_val, max_val, curr))
        # Update Treeview height so that every row is visible.
        num_rows = len(self.tree.get_children())
        self.tree["height"] = num_rows if num_rows > 0 else 1

    def clear_parameters(self):
        self.parameters.clear()
        self.update_parameter_list()
        self.log_message("Parameter list cleared.")

    def log_message(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def on_closing(self):
        if hasattr(self, 'serial_reader'):
            self.serial_reader.stop()
        if hasattr(self, 'ser'):
            self.ser.close()
        self.destroy()

# ----------------- Flask JSON API Backend -----------------


app_api = Flask(__name__)


@app_api.route("/parameters", methods=["GET"])
def api_get_parameters():
    global gui_instance
    if gui_instance:
        params = {}
        for name, param in gui_instance.parameters.items():
            new_param = param.copy()
            try:
                # Try to convert current value to int.
                new_param['current'] = int(new_param['current'])
            except (ValueError, TypeError):
                # If conversion fails, leave the value as is.
                pass
            params[name] = new_param
        return jsonify(params)
    return jsonify({"error": "GUI not available"}), 500


@app_api.route("/parameter/<name>", methods=["GET"])
def api_get_parameter(name):
    global gui_instance
    if gui_instance:
        param = gui_instance.parameters.get(name)
        if param is not None:
            return jsonify({name: param})
        return jsonify({"error": "Parameter not found"}), 404
    return jsonify({"error": "GUI not available"}), 500


@app_api.route("/parameters", methods=["POST"])
def api_add_parameter():
    global gui_instance
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    name = data.get("name")
    min_val = data.get("min")
    max_val = data.get("max")
    current = data.get("current")

    if name is None or min_val is None or max_val is None or current is None:
        return jsonify({"error": "Missing parameter fields"}), 400
    cmd = f"add:param,{name},{min_val},{max_val},{current}"
    gui_instance.thread_safe_send_command(cmd)
    return jsonify({"status": "Command sent", "command": cmd}), 200


@app_api.route("/parameter/<name>", methods=["PUT"])
def api_update_parameter(name):
    global gui_instance
    data = request.get_json()
    print(f"Received data: {data}")  # Log received data to console
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    # Check if the key exists, allowing new_value to be 0
    if "new_value" not in data:
        return jsonify({"error": "Missing new_value field"}), 400
    new_value = data["new_value"]
    # If new_value is boolean, convert it to 0/1
    if isinstance(new_value, bool):
        new_value = 1 if new_value else 0
    cmd = f"update:paramsCurval,{name},{new_value}"
    gui_instance.thread_safe_send_command(cmd)
    return jsonify({"status": "Command sent", "command": cmd}), 200


@app_api.route("/command", methods=["POST"])
def api_send_command():
    global gui_instance
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    command = data.get("command")
    if not command:
        return jsonify({"error": "Missing command field"}), 400
    gui_instance.thread_safe_send_command(command)
    return jsonify({"status": "Command sent", "command": command}), 200


@app_api.route("/software", methods=["POST"])
def api_set_software():
    global gui_instance
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    software_name = data.get("software_name")
    if not software_name:
        return jsonify({"error": "Missing software_name field"}), 400
    cmd = f"set:software,{software_name}"
    gui_instance.thread_safe_send_command(cmd)
    return jsonify({"status": "Command sent", "command": cmd}), 200


@app_api.route("/log", methods=["GET"])
def api_get_log():
    global gui_instance
    if gui_instance:
        log_content = gui_instance.log_text.get("1.0", tk.END)
        return jsonify({"log": log_content})
    return jsonify({"error": "GUI not available"}), 500

# ----------------- End of Flask API -----------------


if __name__ == "__main__":
    serial_port = "/dev/ttyUSB0"
    baud_rate = 9600
    gui_instance = ArduinoGUI(serial_port, baud_rate)

    def run_api():
        # Run Flask app in a separate thread (disable reloader to prevent duplicate threads).
        app_api.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=run_api)
    flask_thread.daemon = True
    flask_thread.start()

    gui_instance.mainloop()

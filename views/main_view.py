import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import logging
import time
from datetime import datetime
import threading
from models.tracker_models import Tracker
from typing import Callable, Any, List
from controllers.main_controller import MainController
from views.history_view import HistoryView

logger = logging.getLogger(__name__)

class MainView:
    def __init__(self, root, controller: MainController):
        self.root = root
        self.controller = controller
        self.controller.set_view(self)
        
        # Load preferences from config
        self.is_dark_mode = self.controller.config.get("gui.dark_mode", False)
        self.auto_scroll = self.controller.config.get("gui.auto_scroll", True)
        
        # Cache for efficient theming
        self._label_widgets: List[tk.Label] = []
        
        # Timer state management
        self._timer_running = False
        self._timer_id = None
        
        self.setup_gui()
        self.setup_bindings()
        self.apply_theme()

    # ===== INITIALIZATION AND SETUP METHODS =====

    def setup_gui(self):
        """Setup the GUI components with label caching"""
        self.root.title("Tracker Manager Pro")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Set application icon if available
        try:
            self.root.iconbitmap("icon.ico")
        except:
            try:
                img = tk.PhotoImage(file="icon.png")
                self.root.iconphoto(True, img)
            except:
                pass
        
        self.create_menu_bar()

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Setup tabs
        self.setup_duplicate_tab()
        self.setup_validation_tab()
        self.setup_results_tab()
        self.setup_history_tab()
        
        # Status bar at bottom
        self.setup_status_bar()

        # Collect all labels for efficient theming
        self._collect_labels(self.root)

    def setup_status_bar(self):
        """Add a status bar at the bottom of the window"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill='x', side='bottom', padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(self.status_frame, textvariable=self.status_var, 
                                   relief='sunken', anchor='w', font=("Arial", 9))
        self.status_label.pack(fill='x')
        
        self._label_widgets.append(self.status_label)

    def setup_duplicate_tab(self):
        """Setup duplicate detection tab with DARK MODE READY layout"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="1. Find Duplicates")
        
        # Input area - Enhanced for dark mode with explicit styling
        input_frame = ttk.LabelFrame(tab, text="Input Trackers", padding=10)
        input_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Header with counter
        header_frame = ttk.Frame(input_frame)
        header_frame.pack(fill='x', pady=(0, 5))
        
        self.input_header = tk.Label(header_frame, text="Paste your tracker list below:", font=("Arial", 10))
        self.input_header.pack(side='left')
        
        self.input_counter = tk.Label(header_frame, text="0 trackers", font=("Arial", 9))
        self.input_counter.pack(side='right')
        
        # Input text area
        self.input_text = scrolledtext.ScrolledText(input_frame, height=12, wrap=tk.WORD, font=("Consolas", 9))
        self.input_text.pack(fill='both', expand=True, pady=(0, 10))
        
        # Bind text change event to update counter
        self.input_text.bind('<KeyRelease>', self.update_input_counter)
        
        # Buttons
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Find Duplicates", 
                command=self.on_find_duplicates).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Clear", 
                command=self.on_clear).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Load from File", 
                command=self.on_load_file).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Sample Data", 
                command=self.load_sample_data).pack(side='left')
        
        # Results area - Enhanced for dark mode
        results_frame = ttk.LabelFrame(tab, text="Results", padding=10)
        results_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        results_header = ttk.Frame(results_frame)
        results_header.pack(fill='x', pady=(0, 5))
        
        self.results_header_label = tk.Label(results_header, text="Unique trackers found:", font=("Arial", 10))
        self.results_header_label.pack(side='left')
        
        self.unique_counter = tk.Label(results_header, text="0 trackers", font=("Arial", 9))
        self.unique_counter.pack(side='right')
        
        # Unique trackers text area
        self.unique_text = scrolledtext.ScrolledText(results_frame, height=8, wrap=tk.WORD, font=("Consolas", 9))
        self.unique_text.pack(fill='both', expand=True)
        
        # Stats with better formatting
        stats_frame = ttk.Frame(results_frame)
        stats_frame.pack(fill='x', pady=5)
        
        self.stats_label = tk.Label(stats_frame, text="Total: 0 | Unique: 0 | Duplicates: 0", 
                                font=("Arial", 10, "bold"))
        self.stats_label.pack(anchor='w')

    def setup_validation_tab(self):
        """Setup validation tab with DARK MODE READY controls"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="2. Validate Trackers")
        
        # Create a main frame with better organization
        main_frame = ttk.Frame(tab)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Network Interface section (Linux only) - Enhanced for dark mode
        if self.controller.is_linux_system():
            interface_frame = ttk.LabelFrame(main_frame, text="Network Interface (Linux Only)", padding=10)
            interface_frame.pack(fill='x', pady=(0, 10))
            
            # Interface selection
            self.interface_label = tk.Label(interface_frame, text="Bind to interface:", font=("Arial", 10))
            self.interface_label.pack(anchor='w', pady=(0, 5))
            
            interface_select_frame = ttk.Frame(interface_frame)
            interface_select_frame.pack(fill='x', pady=5)
            
            self.interface_var = tk.StringVar(value="Auto (default)")
            interfaces = self.controller.get_network_interfaces()
            interface_names = ["Auto (default)"] + [f"{i['name']} ({i['ip']}) - {i['type']}" for i in interfaces]
            
            # Combobox with enhanced styling for dark mode
            self.interface_combo = ttk.Combobox(interface_select_frame, 
                                            textvariable=self.interface_var,
                                            values=interface_names,
                                            state="readonly",
                                            width=50,
                                            font=("Arial", 9))
            self.interface_combo.pack(side='left', padx=(0, 10), fill='x', expand=True)
            
            ttk.Button(interface_select_frame, text="Refresh", 
                    command=self.refresh_interfaces).pack(side='left')
            
            # WAN IP and status in one row
            status_frame = ttk.Frame(interface_frame)
            status_frame.pack(fill='x', pady=(10, 0))
            
            # WAN IP display - Use LabelFrame for better theming
            wan_ip_frame = ttk.LabelFrame(status_frame, text="WAN IP Verification", padding=5)
            wan_ip_frame.pack(side='left', fill='x', expand=True)
            
            wan_ip_content = ttk.Frame(wan_ip_frame)
            wan_ip_content.pack(fill='x', padx=5, pady=2)
            
            self.wan_ip_label = tk.Label(wan_ip_content, text="WAN IP:", font=("Arial", 9))
            self.wan_ip_label.pack(side='left')
            
            self.wan_ip_value = tk.Label(wan_ip_content, text="Unknown", font=("Arial", 9, "bold"))
            self.wan_ip_value.pack(side='left', padx=(5, 15))
            
            ttk.Button(wan_ip_content, text="Check IP", 
                    command=self.check_wan_ip).pack(side='left', padx=(0, 10))
            
            ttk.Button(wan_ip_content, text="Test Interface", 
                    command=self.test_interface).pack(side='left')
            
            # Interface status on the right
            self.interface_status = tk.Label(status_frame, text="Interface: Default", 
                                        font=("Arial", 9))
            self.interface_status.pack(side='right')
            
            # Update status when interface is selected
            if hasattr(self, 'interface_combo'):
                self.interface_combo.bind('<<ComboboxSelected>>', self.on_interface_selected)
        
        # Control section - middle section
        control_frame = ttk.LabelFrame(main_frame, text="Validation Control", padding=10)
        control_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(control_frame, text="Validate unique trackers from previous step:").pack(anchor='w', pady=(0, 10))
        
        # Progress and control frame
        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(fill='x', pady=5)
        
        self.progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress.pack(fill='x', side='left', expand=True, padx=(0, 10))
        
        self.progress_label = tk.Label(progress_frame, text="0/0")
        self.progress_label.pack(side='left', padx=(0, 15))
        
        self.validate_btn = ttk.Button(progress_frame, text="Start Validation", 
                                      command=self.on_start_validation)
        self.validate_btn.pack(side='left', padx=(0, 10))
        
        self.stop_btn = ttk.Button(progress_frame, text="Stop", 
                                  command=self.on_stop_validation,
                                  state='disabled')
        self.stop_btn.pack(side='left')
        
        # Timer and stats row
        stats_frame = ttk.Frame(control_frame)
        stats_frame.pack(fill='x', pady=(5, 0))
        
        self.timer_label = tk.Label(stats_frame, text="Elapsed: 0s")
        self.timer_label.pack(side='left')
        
        self.validation_stats = tk.Label(stats_frame, text="Working: 0 | Dead: 0", font=("Arial", 9))
        self.validation_stats.pack(side='right')
        
        # Results area - bottom section - FIXED VERSION (no grid/pack mixing)
        results_frame = ttk.LabelFrame(main_frame, text="Validation Results", padding=10)
        results_frame.pack(fill='both', expand=True)
        
        # Results header with counters
        results_header = ttk.Frame(results_frame)
        results_header.pack(fill='x', pady=(0, 5))
        
        self.working_label = tk.Label(results_header, text="Working Trackers: 0")
        self.working_label.pack(side='left')
        
        self.dead_label = tk.Label(results_header, text="Dead Trackers: 0")
        self.dead_label.pack(side='right')
        
        # Text areas container
        text_container = ttk.Frame(results_frame)
        text_container.pack(fill='both', expand=True)
        
        # Configure grid for equal 50/50 split
        text_container.columnconfigure(0, weight=1)
        text_container.columnconfigure(1, weight=1)
        text_container.rowconfigure(0, weight=1)

        # Working trackers - left side (50%)
        working_container = ttk.Frame(text_container)
        working_container.grid(row=0, column=0, sticky='nsew', padx=(0, 2))

        self.working_text = scrolledtext.ScrolledText(working_container, height=10, wrap=tk.NONE)  # No word wrap!
        self.working_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Dead trackers - right side (50%)  
        dead_container = ttk.Frame(text_container)
        dead_container.grid(row=0, column=1, sticky='nsew', padx=(2, 0))

        self.dead_text = scrolledtext.ScrolledText(dead_container, height=10, wrap=tk.NONE)  # No word wrap!
        self.dead_text.pack(fill='both', expand=True, padx=5, pady=5)

    def setup_results_tab(self):
        """Setup results tab with enhanced export options"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="3. Export Results")
        
        # Export controls
        export_frame = ttk.LabelFrame(tab, text="Export Options", padding=10)
        export_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(export_frame, text="Export your validated trackers in various formats:").pack(anchor='w', pady=(0, 10))
        
        # Format selection
        format_frame = ttk.Frame(export_frame)
        format_frame.pack(fill='x', pady=5)
        
        self.export_format = tk.StringVar(value="txt")
        ttk.Radiobutton(format_frame, text="Text (TXT)", variable=self.export_format, value="txt").pack(side='left', padx=(0, 10))
        ttk.Radiobutton(format_frame, text="JSON", variable=self.export_format, value="json").pack(side='left', padx=(0, 10))
        ttk.Radiobutton(format_frame, text="CSV", variable=self.export_format, value="csv").pack(side='left', padx=(0, 10))
        
        # Action buttons
        btn_frame = ttk.Frame(export_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Export to File",
                  command=self.on_export_file).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Copy to Clipboard",
                  command=self.on_copy_clipboard).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Copy as Table",
                  command=self.copy_as_table).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Open Preview",
                  command=self.update_preview).pack(side='left')
        
        # Preview area
        preview_frame = ttk.LabelFrame(tab, text="Preview", padding=10)
        preview_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        preview_header = ttk.Frame(preview_frame)
        preview_header.pack(fill='x', pady=(0, 5))
        
        ttk.Label(preview_header, text="Preview:").pack(side='left')
        self.preview_info = tk.Label(preview_header, text="No data to preview", font=("Arial", 9), fg="gray")
        self.preview_info.pack(side='right')
        
        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=15, wrap=tk.WORD)
        self.preview_text.pack(fill='both', expand=True)

    def setup_history_tab(self):
        """Setup history and analytics tab"""
        self.history_view = HistoryView(self.notebook, self.controller)
        self.notebook.add(self.history_view.tab, text="4. History & Analytics")

    def setup_bindings(self):
        """Setup event bindings and keyboard shortcuts"""
        # Always keep essential safety and help bindings
        self.root.bind('<Control-x>', lambda e: self.quit_application())  # Nano-style quit only
        self.root.bind('<Escape>', lambda e: self.on_stop_validation() if hasattr(self, 'stop_btn') and self.stop_btn['state'] == 'normal' else None)
        self.root.bind('<F1>', lambda e: self.show_help())  # F1 help always available
        self.root.protocol("WM_DELETE_WINDOW", self.quit_application)
        
        # Only setup convenience hotkeys if enabled in config
        if self.controller.config.get("gui.enable_hotkeys", False):
            # Ctrl+D to find duplicates
            self.root.bind('<Control-d>', lambda e: self.on_find_duplicates())
            
            # Ctrl+V to validate
            self.root.bind('<Control-v>', lambda e: self.on_start_validation())
            
            # Ctrl+T to toggle theme
            self.root.bind('<Control-t>', lambda e: self.toggle_theme())
            
            # Ctrl+S to save/export
            self.root.bind('<Control-s>', lambda e: self.on_export_file())
            
            # Ctrl+Shift+T for table copy
            self.root.bind('<Control-Shift-T>', lambda e: self.copy_as_table())
            
            logger.info("Hotkeys enabled: Ctrl+D, Ctrl+V, Ctrl+T, Ctrl+S, Ctrl+Shift+T")
        else:
            logger.info("Hotkeys disabled (F1 help and Ctrl-X quit still available)")

    # ===== MENU AND WINDOW MANAGEMENT METHODS =====

    def create_menu_bar(self):
        """Create the application menu bar with enhanced options"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Set menu colors based on current theme
        bg_color = "#1a1a1a" if self.is_dark_mode else "#f5f5f5"
        fg_color = "#e8e8e8" if self.is_dark_mode else "#333333"
        active_bg = "#505050" if self.is_dark_mode else "#e0e0e0"
        
        # Configure main menu bar
        menubar.configure(
            background=bg_color,
            foreground=fg_color,
            activebackground=active_bg,
            activeforeground=fg_color,
            relief="flat",
            bd=0
        )
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0,
                        bg=bg_color,
                        fg=fg_color,
                        activebackground=active_bg,
                        activeforeground=fg_color)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Trackers", command=self.on_load_file)
        file_menu.add_command(label="Export Results", command=self.on_export_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_application)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0,
                        bg=bg_color,
                        fg=fg_color,
                        activebackground=active_bg,
                        activeforeground=fg_color)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Theme", command=self.toggle_theme)
        
        # Auto-scroll variable needs to be tracked
        self.auto_scroll_var = tk.BooleanVar(value=self.auto_scroll)
        view_menu.add_checkbutton(
            label="Auto-scroll Results", 
            variable=self.auto_scroll_var,
            command=self.toggle_auto_scroll
        )
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0,
                            bg=bg_color,
                            fg=fg_color,
                            activebackground=active_bg,
                            activeforeground=fg_color)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Clear All", command=self.on_clear_all)
        tools_menu.add_separator()
        tools_menu.add_command(label="Check WAN IP", command=self.check_wan_ip)
        tools_menu.add_command(label="Refresh Interfaces", command=self.refresh_interfaces)
        tools_menu.add_command(label="Copy as Table", command=self.copy_as_table)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0,
                           bg=bg_color,
                           fg=fg_color,
                           activebackground=active_bg,
                           activeforeground=fg_color)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Quick Help", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)

    def quit_application(self):
        """Safely quit the application - FIXED"""
        try:
            # Stop any ongoing validation
            if hasattr(self.controller, 'is_validating') and self.controller.is_validating:
                self.controller.stop_validation()
            
            # Stop timer
            self.stop_timer()
            
            # Force save using the correct method
            if hasattr(self.controller.config, '_save_config_immediate'):
                self.controller.config._save_config_immediate()
            elif hasattr(self.controller.config, '_flush_pending_saves'):
                self.controller.config._flush_pending_saves()
            
            self.root.quit()
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
            self.root.quit()

    def show_help(self):
        """Show quick help dialog"""
        help_text = """Tracker Manager Pro - Quick Help

Essential Shortcuts (Always Available):
• Ctrl+X - Quit application
• Escape - Stop validation  
• F1 - Show this help

Optional Shortcuts (Enable in Config):
• Ctrl+D - Find duplicates
• Ctrl+V - Validate trackers
• Ctrl+T - Toggle theme
• Ctrl+S - Export results
• Ctrl+Shift+T - Copy as table

Tips:
• Use 'Sample Data' to test the application
• Check the History tab for reliability statistics
• Export results in multiple formats
• On Linux: Use network interface binding for VPN validation
• Use WAN IP verification to confirm interface binding
• Auto-scroll can be toggled in View menu
• Copy as table for spreadsheet-friendly formatting
• Enable optional shortcuts in config for full keyboard control"""

        messagebox.showinfo("Quick Help", help_text)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """Tracker Manager Pro

A comprehensive tool for managing and validating torrent trackers.

Features:
• Duplicate tracker detection
• Multi-threaded validation
• Network interface binding (VPN support)
• WAN IP verification
• Historical analytics dashboard
• Multiple export formats
• Table-formatted clipboard export
• Dark/Light theme support
• Configurable keyboard shortcuts

Version: 2.1
Developed with Python and Tkinter"""
        messagebox.showinfo("About", about_text)

    # ===== THEMING METHODS =====

    def toggle_theme(self):
        """Toggle between light and dark mode and save preference - FIXED"""
        self.is_dark_mode = not self.is_dark_mode
        
        # Save to config - use the correct method signature
        try:
            # Your Config.set() method has immediate parameter
            self.controller.config.set("gui.dark_mode", self.is_dark_mode, immediate=True)
        except TypeError:
            # Fallback if immediate parameter causes issues
            self.controller.config.set("gui.dark_mode", self.is_dark_mode)
            # Force immediate save
            if hasattr(self.controller.config, '_save_config_immediate'):
                self.controller.config._save_config_immediate()
        
        # Apply theme immediately
        self.apply_theme()
        self.update_status(f"Theme changed to {'Dark' if self.is_dark_mode else 'Light'} mode")

    def apply_theme(self):
        """Apply the current theme - ENHANCED DARK MODE CONTRAST"""
        if self.is_dark_mode:
            # Enhanced dark theme with better contrast
            bg_color, fg_color = "#1a1a1a", "#e8e8e8"
            text_bg, text_fg = "#2a2a2a", "#ffffff"  # Better contrast for text areas
            status_bg, status_fg = "#2a2a2a", "#e8e8e8"
            
            # Enhanced color scheme for better visual hierarchy
            self.dark_colors = {
                'bg': bg_color,
                'fg': fg_color,
                'text_bg': text_bg,
                'text_fg': text_fg,
                'accent': "#0078d7",
                'success': "#4CAF50",
                'warning': "#FF9800",
                'error': "#F44336"
            }
        else:
            # Light theme
            bg_color, fg_color = "#f5f5f5", "#333333"
            text_bg, text_fg = "#ffffff", "#000000"
            status_bg, status_fg = "#e0e0e0", "#333333"
            
            self.light_colors = {
                'bg': bg_color,
                'fg': fg_color,
                'text_bg': text_bg,
                'text_fg': text_fg,
                'accent': "#0078d7",
                'success': "#4CAF50",
                'warning': "#FF9800",
                'error': "#F44336"
            }
        
        self.apply_colors(bg_color, fg_color, text_bg, text_fg, status_bg, status_fg)

    def apply_colors(self, bg_color, fg_color, text_bg, text_fg, status_bg, status_fg):
        """Apply colors to all widgets - HEAVILY OPTIMIZED"""
        # Apply to root window
        self.root.configure(bg=bg_color)
        
        # Apply to menu bar
        self.apply_menu_theme(bg_color, fg_color)
        
        # Apply ttk styles first (global) - MAJOR PERFORMANCE BOOST
        self.apply_ttk_styles(bg_color, fg_color)
        
        # Apply status bar
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.configure(bg=status_bg, fg=status_fg)
        
        # Apply to specific widgets (optimized)
        self.apply_to_specific_widgets(bg_color, fg_color, text_bg, text_fg)
        
        # CRITICAL: Fix validation tab labels specifically
        if self.is_dark_mode:
            self._fix_validation_tab_labels(bg_color, fg_color)

    def apply_menu_theme(self, bg_color, fg_color):
        """Apply theme to the menu bar"""
        try:
            menubar = self.root.cget("menu")
            if menubar:
                try:
                    menubar.configure(
                        background=bg_color,
                        foreground=fg_color,
                        activebackground="#505050" if self.is_dark_mode else "#e0e0e0",
                        activeforeground=fg_color,
                        relief="flat",
                        bd=0
                    )
                except:
                    pass
                
                for i in range(menubar.index("end") + 1):
                    try:
                        menu_name = menubar.entrycget(i, "menu")
                        if menu_name:
                            submenu = menubar.nametowidget(menu_name)
                            submenu.configure(
                                background=bg_color,
                                foreground=fg_color,
                                activebackground="#505050" if self.is_dark_mode else "#e0e0e0",
                                activeforeground=fg_color,
                                selectcolor=fg_color,
                                relief="flat",
                                bd=0
                            )
                    except:
                        continue
        except Exception as e:
            logger.debug(f"Menu theming failed: {e}")

    def apply_ttk_styles(self, bg_color, fg_color):
        """Apply styles to ttk widgets - COMPREHENSIVE DARK MODE FIX"""
        style = ttk.Style()
        
        if self.is_dark_mode:
            # DARK THEME - Enhanced with proper LabelFrame theming
            style.configure(".", 
                        background=bg_color, 
                        foreground=fg_color,
                        fieldbackground="#2a2a2a",
                        selectbackground="#404040",
                        selectforeground=fg_color,
                        troughcolor="#404040")
            
            # Base styles
            style.configure("TFrame", background=bg_color)
            style.configure("TLabel", background=bg_color, foreground=fg_color)
            
            # CRITICAL FIX: LabelFrame theming for dark mode
            style.configure("TLabelframe", 
                        background=bg_color, 
                        foreground=fg_color,
                        bordercolor="#404040",  # Border color
                        darkcolor=bg_color,
                        lightcolor=bg_color,
                        relief="solid")  # Explicit relief
            
            style.configure("TLabelframe.Label", 
                        background=bg_color, 
                        foreground=fg_color,
                        font=("Arial", 10, "bold"))
            
            # Apply the style to ALL existing LabelFrames
            self._refresh_all_label_frames()
            
            # Button styles
            style.configure("TButton", 
                        background="#404040", 
                        foreground=fg_color,
                        focuscolor=bg_color,
                        borderwidth=1,
                        relief="raised")
            style.map("TButton",
                    background=[('active', '#505050'), ('pressed', '#606060')],
                    foreground=[('active', fg_color), ('pressed', fg_color)],
                    relief=[('pressed', 'sunken')])
            
            # Notebook styles
            style.configure("TNotebook", background=bg_color)
            style.configure("TNotebook.Tab", 
                        background="#404040", 
                        foreground=fg_color,
                        focuscolor=bg_color,
                        padding=[10, 2])
            style.map("TNotebook.Tab",
                    background=[('selected', '#505050'), ('active', '#484848')],
                    foreground=[('selected', fg_color), ('active', fg_color)])
            
            # Progress bar
            style.configure("Horizontal.TProgressbar", 
                        background="#0078d7",
                        troughcolor=bg_color,
                        bordercolor=bg_color,
                        darkcolor="#0078d7",
                        lightcolor="#0078d7")
            
            # Combobox styles
            style.configure("TCombobox",
                        fieldbackground="#2a2a2a",
                        background="#2a2a2a", 
                        foreground=fg_color,
                        selectbackground="#404040",
                        selectforeground=fg_color,
                        arrowcolor=fg_color,
                        bordercolor="#404040",
                        focuscolor="#404040")
            style.map("TCombobox",
                    fieldbackground=[('readonly', '#2a2a2a')],
                    selectbackground=[('readonly', '#404040')],
                    background=[('readonly', '#2a2a2a')])
            
            # Scrollbar styles
            style.configure("Vertical.TScrollbar",
                        background="#404040",
                        troughcolor=bg_color,
                        bordercolor=bg_color,
                        arrowcolor=fg_color,
                        darkcolor="#404040",
                        lightcolor="#404040")
            style.configure("Horizontal.TScrollbar",
                        background="#404040",
                        troughcolor=bg_color,
                        bordercolor=bg_color,
                        arrowcolor=fg_color,
                        darkcolor="#404040",
                        lightcolor="#404040")
            style.map("Vertical.TScrollbar",
                    background=[('active', '#505050')])
            style.map("Horizontal.TScrollbar",
                    background=[('active', '#505050')])
            
            # Radiobutton styles
            style.configure("TRadiobutton",
                        background=bg_color,
                        foreground=fg_color,
                        indicatorcolor=bg_color,
                        indicatorrelief="raised")
            style.map("TRadiobutton",
                    background=[('active', bg_color)],
                    foreground=[('active', fg_color)])
                    
        else:
            # LIGHT THEME - Clean and professional
            style.configure(".", background=bg_color, foreground=fg_color)
            style.configure("TFrame", background=bg_color)
            style.configure("TLabel", background=bg_color, foreground=fg_color)
            
            # Light theme LabelFrame
            style.configure("TLabelframe", background=bg_color, foreground=fg_color)
            style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)

            # Button styles
            style.configure("TButton", 
                        background=bg_color, 
                        foreground=fg_color)
            style.map("TButton",
                    background=[('active', '#e0e0e0'), ('pressed', '#d0d0d0')],
                    foreground=[('active', fg_color), ('pressed', fg_color)])
            
            # Notebook styles
            style.configure("TNotebook", background=bg_color)
            style.configure("TNotebook.Tab", 
                        background=bg_color, 
                        foreground=fg_color)
            style.map("TNotebook.Tab",
                    background=[('selected', '#e0e0e0'), ('active', '#f0f0f0')],
                    foreground=[('selected', fg_color), ('active', fg_color)])
            
            # Progress bar
            style.configure("Horizontal.TProgressbar", 
                        background="#0078d7",
                        troughcolor=bg_color)
            
            # Combobox styles
            style.configure("TCombobox", 
                        fieldbackground=bg_color,
                        background=bg_color,
                        foreground=fg_color)
            
            # Scrollbar styles
            style.configure("Vertical.TScrollbar",
                        background=bg_color,
                        troughcolor="#e0e0e0")
            style.configure("Horizontal.TScrollbar",
                        background=bg_color,
                        troughcolor="#e0e0e0")
        
        # Force refresh of all ttk widgets
        self._refresh_all_ttk_widgets()

    def apply_to_specific_widgets(self, bg_color, fg_color, text_bg, text_fg):
        """Apply colors to specific widgets - COMPREHENSIVE DARK MODE FIX"""
        # Enhanced text widget theming for dark mode
        text_widgets = [
            self.input_text, self.unique_text, self.working_text,
            self.dead_text, self.preview_text
        ]
        
        for widget in text_widgets:
            if widget and widget.winfo_exists():
                try:
                    # Enhanced dark mode text area styling
                    if self.is_dark_mode:
                        widget.configure(
                            background=text_bg,
                            foreground=text_fg,
                            insertbackground=fg_color,
                            selectbackground="#404040",
                            selectforeground="#ffffff",
                            inactiveselectbackground="#404040",
                            relief="flat",
                            borderwidth=1,
                            highlightthickness=1,
                            highlightcolor="#404040",
                            highlightbackground="#404040"
                        )
                    else:
                        widget.configure(
                            background=text_bg,
                            foreground=text_fg,
                            insertbackground=fg_color,
                            selectbackground="#e0e0e0",
                            selectforeground=text_fg,
                            inactiveselectbackground="#e0e0e0",
                            relief="sunken",
                            borderwidth=1
                        )
                except Exception as e:
                    logger.debug(f"Could not theme text widget: {e}")
        
        # Enhanced combobox theming for dark mode
        if hasattr(self, 'interface_combo') and self.interface_combo.winfo_exists():
            try:
                if self.is_dark_mode:
                    self.interface_combo.configure(
                        background="#2a2a2a",
                        foreground=fg_color,
                        selectbackground="#404040",
                        selectforeground=fg_color
                    )
                else:
                    self.interface_combo.configure(
                        background=bg_color,
                        foreground=fg_color
                    )
            except Exception as e:
                logger.debug(f"Could not theme combobox: {e}")
        
        # ENHANCED: Comprehensive label theming - ADD RECURSIVE METHOD
        self._theme_all_special_labels(bg_color, fg_color)
        self._theme_all_labels_recursive(self.root, bg_color, fg_color)  # ADD THIS LINE
        
        # Enhanced frame theming for better visual hierarchy
        try:
            # Style the status bar differently in dark mode
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                if self.is_dark_mode:
                    self.status_label.configure(bg="#2a2a2a", fg="#e8e8e8")
                else:
                    self.status_label.configure(bg="#e0e0e0", fg="#333333")
        except Exception as e:
            logger.debug(f"Could not theme status bar: {e}")
        
        # History view theming
        if hasattr(self, 'history_view'):
            try:
                self.history_view.apply_theme(bg_color, fg_color, text_bg, text_fg)
            except Exception as e:
                logger.debug(f"Could not theme history view: {e}")

    def _theme_all_special_labels(self, bg_color, fg_color):
        """Theme all special labels comprehensively"""
        # Enhanced label theming for better contrast
        special_labels = [
            'wan_ip_value', 'wan_ip_label', 'interface_status', 'input_counter', 
            'unique_counter', 'working_label', 'dead_label', 'validation_stats', 
            'preview_info', 'stats_label', 'progress_label', 'timer_label',
            'interface_label', 'input_header', 'results_header_label'  # ADDED THESE
        ]
        
        for attr_name in special_labels:
            if hasattr(self, attr_name):
                label_widget = getattr(self, attr_name)
                if label_widget and label_widget.winfo_exists():
                    try:
                        if self.is_dark_mode:
                            # Special styling for important labels in dark mode
                            if attr_name in ['wan_ip_value', 'timer_label', 'validation_stats']:
                                label_widget.configure(bg=bg_color, fg="#ffffff", font=("Arial", 9, "bold"))
                            elif attr_name in ['input_counter', 'unique_counter', 'preview_info']:
                                label_widget.configure(bg=bg_color, fg="#cccccc", font=("Arial", 9))
                            elif attr_name in ['interface_label', 'wan_ip_label', 'input_header', 'results_header_label']:
                                # CRITICAL FIX: These are the white labels in both tabs
                                label_widget.configure(bg=bg_color, fg=fg_color, font=("Arial", 10))
                                logger.info(f"Themed {attr_name} label")
                            else:
                                label_widget.configure(bg=bg_color, fg=fg_color)
                        else:
                            label_widget.configure(bg=bg_color, fg=fg_color)
                    except Exception as e:
                        logger.debug(f"Could not theme label {attr_name}: {e}")
        
        # MANUALLY THEME SPECIFIC LABELS THAT ARE STILL WHITE
        try:
            # Theme the header labels in duplicate tab
            if hasattr(self, 'input_header') and self.input_header.winfo_exists():
                self.input_header.configure(bg=bg_color, fg=fg_color)
            if hasattr(self, 'results_header_label') and self.results_header_label.winfo_exists():
                self.results_header_label.configure(bg=bg_color, fg=fg_color)
            
            # CRITICAL: Directly theme the validation tab labels we know exist
            validation_labels_to_fix = [
                'interface_label', 'wan_ip_label'
            ]
            
            for label_name in validation_labels_to_fix:
                if hasattr(self, label_name):
                    label = getattr(self, label_name)
                    if label and label.winfo_exists():
                        label.configure(bg=bg_color, fg=fg_color)
                        logger.info(f"Directly themed {label_name}")
                        
        except Exception as e:
            logger.debug(f"Could not theme specific headers: {e}")

    def _fix_validation_tab_labels(self, bg_color, fg_color):
        """Manually fix specific labels in validation tab that remain white"""
        try:
            # Get the validation tab (tab index 1)
            validation_tab = self.notebook.nametowidget(self.notebook.tabs()[1])
            
            # Find the main frame in validation tab
            for child in validation_tab.winfo_children():
                if isinstance(child, ttk.Frame):  # Main frame
                    for main_child in child.winfo_children():
                        # Look for Network Interface LabelFrame
                        if (isinstance(main_child, ttk.LabelFrame) and 
                            "Network Interface" in main_child.cget("text")):
                            
                            # Fix "Bind to interface:" label
                            for frame_child in main_child.winfo_children():
                                if isinstance(frame_child, tk.Label) and "Bind to interface:" in frame_child.cget("text"):
                                    frame_child.configure(bg=bg_color, fg=fg_color)
                                    logger.info("Fixed 'Bind to interface:' label")
                                
                                # Look for WAN IP LabelFrame inside the Network Interface frame
                                elif isinstance(frame_child, ttk.Frame):
                                    for sub_child in frame_child.winfo_children():
                                        if isinstance(sub_child, ttk.LabelFrame) and "WAN IP" in sub_child.cget("text"):
                                            # Fix labels inside WAN IP frame
                                            for wan_child in sub_child.winfo_children():
                                                if isinstance(wan_child, ttk.Frame):
                                                    for label_child in wan_child.winfo_children():
                                                        if isinstance(label_child, tk.Label) and "WAN IP:" in label_child.cget("text"):
                                                            label_child.configure(bg=bg_color, fg=fg_color)
                                                            logger.info("Fixed 'WAN IP:' label")
            
            # Alternative method: Directly target the specific label attributes we know exist
            if hasattr(self, 'interface_label') and self.interface_label.winfo_exists():
                self.interface_label.configure(bg=bg_color, fg=fg_color)
                logger.info("Fixed interface_label via attribute")
            
            # Find and fix any WAN IP label
            if hasattr(self, 'wan_ip_label') and self.wan_ip_label.winfo_exists():
                self.wan_ip_label.configure(bg=bg_color, fg=fg_color)
                logger.info("Fixed wan_ip_label via attribute")
                
        except Exception as e:
            logger.debug(f"Could not fix validation tab labels: {e}")

    def _theme_all_labels_recursive(self, parent, bg_color, fg_color):
        """Recursively theme ALL labels in the entire application"""
        try:
            for child in parent.winfo_children():
                # Theme regular tk Labels
                if isinstance(child, tk.Label):
                    try:
                        child.configure(bg=bg_color, fg=fg_color)
                    except Exception as e:
                        logger.debug(f"Could not theme label {child}: {e}")
                
                # Recursively theme children
                if hasattr(child, 'winfo_children'):
                    self._theme_all_labels_recursive(child, bg_color, fg_color)
                    
        except Exception as e:
            logger.debug(f"Error in recursive label theming: {e}")

    def _collect_labels(self, parent):
        """Collect all Label widgets for efficient theming"""
        try:
            for child in parent.winfo_children():
                if child.winfo_class() == 'Label':
                    self._label_widgets.append(child)
                if child.winfo_children():
                    self._collect_labels(child)
        except Exception as e:
            logger.debug(f"Could not collect labels from {parent}: {e}")

    def _refresh_all_label_frames(self):
        """Refresh all LabelFrame widgets to apply new styles"""
        try:
            # Find and refresh all LabelFrame widgets
            def refresh_widgets(parent):
                for child in parent.winfo_children():
                    if isinstance(child, ttk.LabelFrame):
                        # Reconfigure the LabelFrame
                        child.configure(style='TLabelframe')
                    if child.winfo_children():
                        refresh_widgets(child)
            
            refresh_widgets(self.root)
        except Exception as e:
            logger.debug(f"Could not refresh LabelFrames: {e}")

    def _refresh_all_ttk_widgets(self):
        """Refresh all ttk widgets to apply new styles"""
        try:
            # Force Tkinter to update all styles
            self.root.update_idletasks()
        except Exception as e:
            logger.debug(f"Could not refresh ttk widgets: {e}")

    def _safe_config_save(self):
        """Safely save configuration - SIMPLIFIED"""
        try:
            # Just use the method we know works
            if hasattr(self.controller.config, '_save_config_immediate'):
                self.controller.config._save_config_immediate()
                return True
        except Exception as e:
            logger.error(f"Config save failed: {e}")
        
        return False

    # ===== NETWORK INTERFACE METHODS =====

    def on_interface_selected(self, event):
        """Handle interface selection"""
        selected = self.interface_var.get()
        if selected != "Auto (default)":
            interface_name = selected.split(' ')[0]
            self.interface_status.config(
                text=f"Interface: {interface_name} ✅", 
                fg="green"
            )
            # Auto-check WAN IP when interface changes
            self.root.after(500, self.check_wan_ip)
        else:
            self.interface_status.config(
                text="Interface: Default", 
                fg="gray"
            )
            self.check_wan_ip()

    def check_wan_ip(self):
        """Check and display the current WAN IP with enhanced safety"""
        def check():
            try:
                if hasattr(self, 'interface_var'):
                    interface_name = None
                    if self.interface_var.get() != "Auto (default)":
                        interface_name = self.interface_var.get().split(' ')[0]
                    
                    self.controller.set_validation_interface(interface_name)
                    external_ip = self.controller.validator.get_external_ip()
                    
                    # Enhanced safety check
                    def update_ip():
                        if hasattr(self, 'wan_ip_value') and self.wan_ip_value.winfo_exists():
                            self.wan_ip_value.config(
                                text=external_ip,
                                fg="red" if "failed" in external_ip.lower() else "green"
                            )
                    
                    self.safe_gui_update(update_ip)
                    self.update_status(f"WAN IP: {external_ip}")
            except Exception as e:
                logger.error(f"Error checking WAN IP: {e}")
                def show_error():
                    if hasattr(self, 'wan_ip_value') and self.wan_ip_value.winfo_exists():
                        self.wan_ip_value.config(text=f"Error: {e}", fg="red")
                self.safe_gui_update(show_error)
        
        threading.Thread(target=check, daemon=True).start()

    def test_interface(self):
        """Test the currently selected interface with enhanced error handling"""
        try:
            if hasattr(self, 'interface_var'):
                interface_name = None
                if self.interface_var.get() != "Auto (default)":
                    interface_name = self.interface_var.get().split(' ')[0]
                
                self.controller.set_validation_interface(interface_name)
                
                # Quick test to httpbin.org to see our IP
                import requests
                with requests.Session() as session:
                    if interface_name:
                        session = self.controller.validator.interface_binder.bind_to_interface(session, interface_name)
                        interface_info = f" via {interface_name}"
                    else:
                        interface_info = " (default)"
                    
                    response = session.get('https://httpbin.org/ip', timeout=10)
                    ip_data = response.json()
                    external_ip = ip_data.get('origin', 'Unknown')
                    
                    messagebox.showinfo("Interface Test", 
                                      f"Interface: {interface_name or 'Default'}\n"
                                      f"External IP: {external_ip}\n"
                                      f"Status: ✅ Working")
                    self.update_status(f"Interface test: {external_ip}{interface_info}")
                    
                    # Update WAN IP display
                    def update_display():
                        if hasattr(self, 'wan_ip_value') and self.wan_ip_value.winfo_exists():
                            self.wan_ip_value.config(text=external_ip, fg="green")
                    self.safe_gui_update(update_display)
        except Exception as e:
            messagebox.showerror("Interface Test Failed", f"Error: {e}")
            self.update_status("Interface test failed")
            def show_error():
                if hasattr(self, 'wan_ip_value') and self.wan_ip_value.winfo_exists():
                    self.wan_ip_value.config(text=f"Test failed: {e}", fg="red")
            self.safe_gui_update(show_error)

    def refresh_interfaces(self):
        """Refresh network interfaces list with error handling"""
        try:
            if hasattr(self, 'interface_combo'):
                interfaces = self.controller.get_network_interfaces()
                interface_names = ["Auto (default)"] + [f"{i['name']} ({i['ip']}) - {i['type']}" for i in interfaces]
                self.interface_combo['values'] = interface_names
                self.update_status("Network interfaces refreshed")
        except Exception as e:
            logger.error(f"Error refreshing interfaces: {e}")
            self.update_status("Error refreshing interfaces")

    # ===== DATA MANAGEMENT METHODS =====

    def load_sample_data(self):
        """Load sample tracker data for testing"""
        sample_trackers = """udp://tracker.opentrackr.org:1337/announce
http://tracker.openbittorrent.com:80/announce
udp://9.rarbg.to:2710/announce
udp://tracker.opentrackr.org:1337/announce
http://tracker.openbittorrent.com:80/announce
udp://open.stealth.si:80/announce"""
        
        self.input_text.delete('1.0', tk.END)
        self.input_text.insert('1.0', sample_trackers)
        self.update_input_counter()
        self.update_status("Sample data loaded")

    def update_input_counter(self, event=None):
        """Update the input tracker counter"""
        try:
            text = self.input_text.get('1.0', 'end-1c')
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            count = len(lines)
            self.input_counter.config(text=f"{count} trackers")
        except Exception as e:
            logger.debug(f"Error updating input counter: {e}")

    # ===== EVENT HANDLER METHODS =====

    def on_find_duplicates(self):
        try:
            text = self.input_text.get('1.0', tk.END).strip()
            if not text:
                messagebox.showwarning("Warning", "Please enter some tracker URLs first!")
                return
                
            self.update_status("Finding duplicates...")
            stats = self.controller.find_duplicates(text)
            
            self.unique_text.delete('1.0', tk.END)
            unique_urls = self.controller.trackers.unique_urls
            self.unique_text.insert('1.0', '\n'.join(unique_urls))
            
            self.stats_label.config(
                text=f"Total: {stats['total']} | Unique: {stats['unique']} | Duplicates: {stats['duplicates']}"
            )
            
            # Update counters
            self.unique_counter.config(text=f"{stats['unique']} trackers")
            
            self.notebook.select(1)  # Switch to validation tab
            self.update_status(f"Found {stats['unique']} unique trackers out of {stats['total']} total")
            
            # Auto-start validation if few trackers
            if stats['unique'] <= 50:
                self.root.after(1000, lambda: messagebox.showinfo("Ready", 
                    f"Found {stats['unique']} unique trackers. Ready to validate!"))
            
        except ValueError as e:
            messagebox.showwarning("Warning", str(e))
            self.update_status("Error finding duplicates")
        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            messagebox.showerror("Error", f"An error occurred: {e}")
            self.update_status("Error finding duplicates")
    
    def on_clear(self):
        """Clear current tab data"""
        self.input_text.delete('1.0', tk.END)
        self.unique_text.delete('1.0', tk.END)
        self.stats_label.config(text="Total: 0 | Unique: 0 | Duplicates: 0")
        self.input_counter.config(text="0 trackers")
        self.unique_counter.config(text="0 trackers")
        self.controller.trackers.clear()
        self.update_status("Data cleared")
    
    def on_clear_all(self):
        """Clear all data across tabs"""
        self.on_clear()
        self.working_text.delete('1.0', tk.END)
        self.dead_text.delete('1.0', tk.END)
        self.preview_text.delete('1.0', tk.END)
        self.progress['value'] = 0
        self.progress_label.config(text="0/0")
        self.timer_label.config(text="Elapsed: 0s")
        self.working_label.config(text="Working Trackers: 0")
        self.dead_label.config(text="Dead Trackers: 0")
        self.validation_stats.config(text="Working: 0 | Dead: 0")
        self.preview_info.config(text="No data to preview")
        self.update_status("All data cleared")
    
    def on_load_file(self):
        file_path = filedialog.askopenfilename(
            title="Load Tracker List",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.input_text.delete('1.0', tk.END)
                self.input_text.insert('1.0', content)
                self.update_input_counter()
                self.update_status(f"Loaded trackers from {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not load file: {e}")
                self.update_status("Error loading file")
    
    def on_start_validation(self):
        try:
            if not self.controller.trackers.unique_urls:
                messagebox.showwarning("Warning", "No trackers to validate! Find duplicates first.")
                return
                
            # Reset UI state
            self.working_text.delete('1.0', tk.END)
            self.dead_text.delete('1.0', tk.END)
            self.working_label.config(text="Working Trackers: 0")
            self.dead_label.config(text="Dead Trackers: 0")
            self.validation_stats.config(text="Working: 0 | Dead: 0")
            self.progress['value'] = 0
            
            # Set network interface before validation (Linux only)
            if hasattr(self, 'interface_var') and self.interface_var.get() != "Auto (default)":
                interface_name = self.interface_var.get().split(' ')[0]
                self.controller.set_validation_interface(interface_name)
                self.update_status(f"Validation using interface: {interface_name}")
            else:
                self.controller.set_validation_interface(None)
                self.update_status("Validation using default interface")
                
            self.controller.start_validation()
            self.validate_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            self.start_time = time.time()
            self.update_status("Validation started...")
            
            # Start the timer
            self.start_timer()
            
        except ValueError as e:
            messagebox.showwarning("Warning", str(e))
        except Exception as e:
            logger.error(f"Error starting validation: {e}")
            messagebox.showerror("Error", f"Failed to start validation: {e}")
            self.update_status("Error starting validation")
    
    def on_stop_validation(self):
        """Stop validation and clean up"""
        try:
            self.controller.stop_validation()
            self.validate_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.stop_timer()
            self.update_status("Validation stopped by user")
        except Exception as e:
            logger.error(f"Error stopping validation: {e}")
    
    def on_validation_complete(self, working_count: int, total_count: int, elapsed: float):
        """Called when validation completes"""
        try:
            self.validate_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.stop_timer()
            
            # Final timer update
            if hasattr(self, 'start_time'):
                final_elapsed = int(time.time() - self.start_time)
                self.timer_label.config(text=f"Elapsed: {final_elapsed}s (Completed)")
            
            success_rate = (working_count / total_count * 100) if total_count > 0 else 0
            message = f"Validation finished! Working: {working_count}/{total_count} ({success_rate:.1f}%) - Time: {elapsed:.2f}s"
            
            self.update_status(message)
            self.update_preview()
            self.notebook.select(2)  # Switch to results tab
            
            # Show completion message
            self.root.after(100, lambda: messagebox.showinfo("Complete", message))
            
        except Exception as e:
            logger.error(f"Error in validation completion: {e}")

    # ===== EXPORT AND COPY METHODS =====

    def update_preview(self):
        """Update results preview based on selected format"""
        try:
            format_type = self.export_format.get()
            
            if format_type == "txt":
                content = self.controller.export_working_trackers()
                self.preview_info.config(text="Text format (TXT)")
            elif format_type == "json":
                import json
                data = self.controller.export_all_results()
                content = json.dumps(data, indent=2, ensure_ascii=False)
                self.preview_info.config(text="JSON format")
            elif format_type == "csv":
                content = self.controller.export_csv()
                self.preview_info.config(text="CSV format")
            else:
                content = "Unsupported format"
                self.preview_info.config(text="Unsupported format")
            
            self.preview_text.delete('1.0', tk.END)
            if content.strip():
                self.preview_text.insert('1.0', content)
                line_count = len(content.splitlines())
                self.preview_info.config(text=f"{self.preview_info.cget('text')} - {line_count} lines")
            else:
                self.preview_text.insert('1.0', "No data available for preview")
                self.preview_info.config(text="No data to preview")
                
        except Exception as e:
            logger.error(f"Error updating preview: {e}")
            self.preview_text.delete('1.0', tk.END)
            self.preview_text.insert('1.0', f"Error generating preview: {e}")
    
    def on_export_file(self):
        """Export results based on selected format"""
        try:
            format_type = self.export_format.get()
            
            if format_type == "txt":
                content = self.controller.export_working_trackers()
                file_types = [("Text files", "*.txt"), ("All files", "*.*")]
                defaultextension = ".txt"
            elif format_type == "json":
                import json
                data = self.controller.export_all_results()
                content = json.dumps(data, indent=2, ensure_ascii=False)
                file_types = [("JSON files", "*.json"), ("All files", "*.*")]
                defaultextension = ".json"
            elif format_type == "csv":
                content = self.controller.export_csv()
                file_types = [("CSV files", "*.csv"), ("All files", "*.*")]
                defaultextension = ".csv"
            else:
                messagebox.showerror("Error", "Unsupported export format")
                return
            
            if not content.strip():
                messagebox.showwarning("Warning", "No data to export!")
                return
                
            file_path = filedialog.asksaveasfilename(
                defaultextension=defaultextension,
                filetypes=file_types,
                title=f"Export Results as {format_type.upper()}"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                trackers_count = len(content.splitlines())
                messagebox.showinfo("Success", f"Exported {trackers_count} items to {file_path}")
                self.update_status(f"Exported {trackers_count} items to {format_type.upper()}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
            self.update_status("Export failed")
    
    def on_copy_clipboard(self):
        try:
            format_type = self.export_format.get()
            
            if format_type == "txt":
                content = self.controller.export_working_trackers()
            elif format_type == "json":
                import json
                data = self.controller.export_all_results()
                content = json.dumps(data, indent=2, ensure_ascii=False)
            elif format_type == "csv":
                content = self.controller.export_csv()
            else:
                content = ""
            
            if not content.strip():
                messagebox.showwarning("Warning", "No data to copy!")
                return
                
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            
            items_count = len(content.splitlines())
            messagebox.showinfo("Success", f"Copied {items_count} items to clipboard!")
            self.update_status(f"Copied {items_count} items to clipboard")
            
        except Exception as e:
            messagebox.showerror("Error", f"Copy failed: {e}")
            self.update_status("Copy to clipboard failed")

    def copy_as_table(self):
        """Copy working trackers as tab-separated table for spreadsheets"""
        try:
            working_trackers = [tracker.url for tracker in self.controller.trackers.working_trackers]
            if not working_trackers:
                messagebox.showwarning("Warning", "No working trackers to copy!")
                return
            
            # Create tab-separated table
            table_content = '\t'.join(working_trackers)
            
            self.root.clipboard_clear()
            self.root.clipboard_append(table_content)
            
            messagebox.showinfo("Success", f"Copied {len(working_trackers)} trackers as table to clipboard!\n\nPaste into Excel/Google Sheets as tab-separated data.")
            self.update_status(f"Copied {len(working_trackers)} trackers as table")
            
        except Exception as e:
            messagebox.showerror("Error", f"Table copy failed: {e}")
            self.update_status("Table copy failed")

    # ===== UTILITY AND HELPER METHODS =====

    def show_error(self, message: str):
        """Show error message - used by controller"""
        messagebox.showerror("Error", message)
    
    def show_info(self, message: str):
        """Show info message"""
        messagebox.showinfo("Information", message)
    
    def safe_gui_update(self, func: Callable, *args, **kwargs):
        """Enhanced safe GUI update with comprehensive safety checks"""
        def update():
            try:
                # Comprehensive widget existence checking
                if (self.root and 
                    hasattr(self.root, 'winfo_exists') and 
                    self.root.winfo_exists() and
                    hasattr(func, '__call__')):
                    func(*args, **kwargs)
            except tk.TclError as e:
                logger.debug(f"GUI update skipped (widget destroyed): {e}")
            except Exception as e:
                logger.error(f"GUI update failed: {e}")
        
        try:
            if self.root and hasattr(self.root, 'after'):
                self.root.after(0, update)
        except Exception as e:
            logger.error(f"Could not schedule GUI update: {e}")

    def update_status(self, message: str):
        """Update status bar message"""
        logger.info(f"Status: {message}")
        self.safe_gui_update(lambda: self.status_var.set(message))

    def toggle_auto_scroll(self):
        """Toggle auto-scroll feature"""
        self.auto_scroll = self.auto_scroll_var.get()
        self.controller.config.set("gui.auto_scroll", self.auto_scroll)
        status = "enabled" if self.auto_scroll else "disabled"
        self.update_status(f"Auto-scroll {status}")

    # ===== TIMER METHODS =====

    def start_timer(self):
        """Start the elapsed time timer"""
        self._timer_running = True
        self._update_timer()
    
    def stop_timer(self):
        """Stop the elapsed time timer"""
        self._timer_running = False
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
    
    def _update_timer(self):
        """Update the elapsed time display - FIXED COMPLETE VERSION"""
        if not self._timer_running:
            return
        
        try:
            if hasattr(self, 'start_time'):
                elapsed = int(time.time() - self.start_time)
                minutes = elapsed // 60
                seconds = elapsed % 60
                if minutes > 0:
                    self.timer_label.config(text=f"Elapsed: {minutes}m {seconds}s")
                else:
                    self.timer_label.config(text=f"Elapsed: {seconds}s")
            
            # Schedule next update
            self._timer_id = self.root.after(1000, self._update_timer)
        except Exception as e:
            logger.debug(f"Timer update error: {e}")
            self._timer_running = False

    # ===== PROGRESS AND UPDATE METHODS =====

    def update_progress(self, percent, current, total):
        """Update progress bar and label with bounds checking"""
        self.safe_gui_update(lambda: self._update_progress_internal(percent, current, total))
    
    def _update_progress_internal(self, percent, current, total):
        """Internal progress update (called from safe_gui_update)"""
        try:
            if hasattr(self, 'progress') and self.progress.winfo_exists():
                safe_percent = max(0, min(100, percent))
                self.progress['value'] = safe_percent
                
            if hasattr(self, 'progress_label') and self.progress_label.winfo_exists():
                self.progress_label.config(text=f"{current}/{total}")
                
            self.update_status(f"Validating... {current}/{total} ({safe_percent:.1f}%)")
        except Exception as e:
            logger.debug(f"Progress update failed: {e}")

    def append_tracker_result(self, tracker):
        """Append a single tracker result to the appropriate text area"""
        self.safe_gui_update(lambda: self._append_tracker_result_internal(tracker))
    
    def _append_tracker_result_internal(self, tracker):
        """Internal tracker result append (called from safe_gui_update)"""
        try:
            text_widget = self.working_text if tracker.alive else self.dead_text
            counter_label = self.working_label if tracker.alive else self.dead_label
            
            # Enhanced safety checks
            if not (text_widget and text_widget.winfo_exists()):
                return
            if not (counter_label and counter_label.winfo_exists()):
                return
            
            status_icon = "✅" if tracker.alive else "❌"
            response_time = f" ({tracker.response_time:.2f}s)" if tracker.response_time else ""
            
            # Add interface info if bound
            interface_info = ""
            if hasattr(self.controller.validator, 'bound_interface') and self.controller.validator.bound_interface:
                interface_info = f" [via {self.controller.validator.bound_interface}]"
            
            text_widget.insert(tk.END, f"{status_icon} {tracker.url}{response_time}{interface_info}\n")
            
            # Update counter
            current_text = counter_label.cget("text")
            count = int(current_text.split(": ")[1]) + 1
            counter_label.config(text=f"{current_text.split(':')[0]}: {count}")
            
            # Update validation stats
            if (hasattr(self, 'working_label') and self.working_label.winfo_exists() and
                hasattr(self, 'dead_label') and self.dead_label.winfo_exists() and
                hasattr(self, 'validation_stats') and self.validation_stats.winfo_exists()):
                
                working_count = int(self.working_label.cget("text").split(": ")[1])
                dead_count = int(self.dead_label.cget("text").split(": ")[1])
                self.validation_stats.config(text=f"Working: {working_count} | Dead: {dead_count}")
            
            # Only auto-scroll if enabled
            if self.auto_scroll:
                text_widget.see(tk.END)
                
        except Exception as e:
            logger.debug(f"Could not append tracker result: {e}")
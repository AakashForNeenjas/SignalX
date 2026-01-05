import json
import os
import sys
from typing import Dict, Any, Callable
from core.DBCParser import DBCParser, resource_path

class SignalManager:
    """Manage CAN signal decoding and UI updates based on DBC and mapping configuration"""
    
    def __init__(self, dbc_parser: DBCParser, config_folder="CAN Configuration"):
        self.dbc_parser = dbc_parser
        self.config_folder = config_folder
        self.signal_mappings = []
        self.ui_update_callbacks = {}  # {ui_element_name: callback_function}
        
    def load_signal_mapping(self, filename="signal_mapping.json"):
        """Load signal-to-UI mapping configuration"""
        try:
            config_path = resource_path(os.path.join(self.config_folder, filename))
            
            if not os.path.exists(config_path):
                print(f"Signal mapping file not found: {config_path}")
                return False, f"Mapping file not found"
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.signal_mappings = config.get('signal_mappings', [])
            
            print(f"✓ Loaded {len(self.signal_mappings)} signal mappings")
            return True, f"Loaded {len(self.signal_mappings)} mappings"
            
        except Exception as e:
            print(f"Failed to load signal mapping: {e}")
            return False, f"Failed to load mapping: {e}"
    
    def register_ui_callback(self, ui_element_name: str, callback: Callable):
        """
        Register a callback function for a UI element.
        Callback signature: callback(value, signal_type)
        """
        self.ui_update_callbacks[ui_element_name] = callback
    
    def process_can_message(self, msg_id: int, data: bytes):
        """
        Process a CAN message: decode it and update mapped UI elements
        """
        # Decode message using DBC
        decoded_signals = self.dbc_parser.decode_message(msg_id, data)
        
        if not decoded_signals:
            return  # Message not in DBC or decoding failed
        
        # Update UI elements based on signal mappings
        for mapping in self.signal_mappings:
            dbc_signal = mapping['dbc_signal']
            ui_element = mapping['ui_element']
            signal_type = mapping['type']
            
            # Check if this signal was in the decoded message
            if dbc_signal in decoded_signals:
                value = decoded_signals[dbc_signal]
                
                # Update UI element if callback is registered
                if ui_element in self.ui_update_callbacks:
                    callback = self.ui_update_callbacks[ui_element]
                    
                    if signal_type == "value":
                        # Update value display
                        callback(value, "value")
                    
                    elif signal_type == "status":
                        # Update status indicator (LED)
                        error_value = mapping.get('error_value', 1)
                        is_error = (value == error_value)
                        callback(is_error, "status")
    
    def get_signal_value(self, signal_name: str, msg_id: int, data: bytes):
        """Get a specific signal value from a CAN message"""
        decoded = self.dbc_parser.decode_message(msg_id, data)
        if decoded and signal_name in decoded:
            return decoded[signal_name]
        return None
    
    def list_mapped_signals(self):
        """List all configured signal mappings"""
        return [(m['dbc_signal'], m['ui_element'], m['type']) for m in self.signal_mappings]

import cantools
import os
import sys
from typing import Dict, Optional, Any


def resource_path(rel_path: str) -> str:
    """
    Resolve a path that works both in development and in a PyInstaller bundle.
    """
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)

class DBCParser:
    """Parse and manage DBC files for CAN message decoding"""
    
    def __init__(self, dbc_folder="DBC"):
        self.dbc_folder = dbc_folder
        self.database = None
        self.dbc_file_path = None
        
    def load_dbc_file(self, filename=None):
        """
        Load a DBC file from the DBC folder.
        If filename is None, loads the first .dbc file found.
        """
        try:
            dbc_root = resource_path(self.dbc_folder)
            # Create DBC folder if it doesn't exist
            if not os.path.exists(dbc_root):
                os.makedirs(dbc_root, exist_ok=True)
                print(f"Created DBC folder: {dbc_root}")
                return False, "DBC folder created, please add DBC file"
            
            # Find DBC file
            if filename:
                dbc_path = os.path.join(dbc_root, filename if filename.endswith('.dbc') else f"{filename}.dbc")
            else:
                # Find first .dbc file in folder
                dbc_files = [f for f in os.listdir(dbc_root) if f.endswith('.dbc')]
                if not dbc_files:
                    return False, f"No DBC files found in {dbc_root}"
                dbc_path = os.path.join(dbc_root, dbc_files[0])
            
            if not os.path.exists(dbc_path):
                return False, f"DBC file not found: {dbc_path}"
            
            # Load DBC file
            self.database = cantools.database.load_file(dbc_path)
            self.dbc_file_path = dbc_path
            
            print(f"✓ Loaded DBC file: {os.path.basename(dbc_path)}")
            print(f"  Messages: {len(self.database.messages)}")
            
            return True, f"Loaded DBC: {os.path.basename(dbc_path)} ({len(self.database.messages)} messages)"
            
        except Exception as e:
            return False, f"Failed to load DBC: {e}"
    
    def decode_message(self, msg_id: int, data: bytes) -> Optional[Dict[str, Any]]:
        """
        Decode a CAN message using the loaded DBC database.
        Returns a dictionary of signal names and values.
        """
        if not self.database:
            return None
        
        try:
            # Find message by ID
            message = self.database.get_message_by_frame_id(msg_id)
            
            # Decode message data
            decoded = message.decode(data)
            
            return decoded
            
        except Exception as e:
            # Message ID not in DBC or decoding error
            return None
    
    def get_signal_info(self, signal_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific signal"""
        if not self.database:
            return None
        
        for message in self.database.messages:
            for signal in message.signals:
                if signal.name == signal_name:
                    return {
                        'name': signal.name,
                        'unit': signal.unit,
                        'min': signal.minimum,
                        'max': signal.maximum,
                        'offset': signal.offset,
                        'scale': signal.scale,
                        'message_id': message.frame_id,
                        'message_name': message.name
                    }
        return None
    
    def get_all_signals(self) -> Dict[str, Dict[str, Any]]:
        """Get all signals from the DBC database"""
        if not self.database:
            return {}
        
        signals = {}
        for message in self.database.messages:
            for signal in message.signals:
                signals[signal.name] = {
                    'unit': signal.unit,
                    'min': signal.minimum,
                    'max': signal.maximum,
                    'message_id': message.frame_id,
                    'message_name': message.name
                }
        return signals
    
    def list_messages(self):
        """List all messages in the DBC"""
        if not self.database:
            return []
        
        messages = []
        for msg in self.database.messages:
            messages.append({
                'id': msg.frame_id,
                'name': msg.name,
                'length': msg.length,
                'signals': [s.name for s in msg.signals]
            })
        return messages

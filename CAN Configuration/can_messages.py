"""
CAN Configuration for AtomX
This file defines the cyclic CAN messages to be transmitted.
Messages are defined with their signal values based on the DBC file.
"""

# CAN Message Configuration
# Format: message_name: {message_id, data, cycle_time_ms}
# Data will be encoded using the DBC file definitions

CYCLIC_CAN_MESSAGES = {
    # Vehicle Mode Message
    'Vehicle_Mode': {
        'signals': {
            'Vehicle_Mode_Lvl_1': 5,
            'Vehicle_Mode_Lvl_2': 15,
            'Vehicle_Mode_Lvl_3': 1
        },
        'cycle_time': 100  # ms
    },
    
    # VCU Data Message
    'VCU_Data': {
        'signals': {
            'Ignition_Sts': 1,
            'Chrgr_Plugin': 0,
            'HU_Power_Supply': 0,
            'MCU_Power_Supply': 0,
            'Left_Indicator_Power_Supply': 0,
            'Right_Indicator_Power_Supply': 0,
            'High_Beam_Power_Supply': 0,
            'Low_Beam_Power_Supply': 0,
            'Position_Lamp_Power_Supply': 0,
            'LSC_Power_Supply': 0,
            'RSC_Power_Supply': 0,
            'Horn_Power_Supply': 0,
            'Speaker_Power_Supply': 0,
            'SOM_Power_Supply': 0,
            'EHBL_Commands': 0,
            'EHBL_Power_Supply': 0,
            'Stop_Lamp_Power_Supply': 0,
            'Tail_Lamp_Power_Supply': 0,
            'Veh_Authentication_Flag': 0,
            'Tail_Lamp_Sts': 0,
            'Stop_Lamp_Sts': 0,
            'Drv_Enable': 0,
            'Cruise_Availibilty_Status': 0,
            'Throttle_Response_CutOFF_Flag': 0,
            'Auto_Lock_Flg': 0,
            'BMS_Hearbeat_Fail_flg': 0,
            'MCU_Hearbeat_Fail_flg': 0,
            'OBC_Hearbeat_Fail_flg': 0,
            'SPI_Comm_Fail_flg': 0,
            'LIN_Comm_Fail_flg': 0,
            'BCM_RTC_WakeUp_flg': 0
        },
        'cycle_time': 100  # ms
    },
    
    # BMS Parameter 1 Message
    'BMS_PARAMETER_1': {
        'signals': {
            'BMS_Mode': 2,
            'BMS_Regen_Inhibit': 0,
            'DisChrg_Contactor_state': 1,
            'Chrg_Contactor_state': 1,
            'PreChrg_Contactor_state': 0,
            'BMS_Board_Temp': 0,
            'Batt_Pack_Bus_Vlt': 0,
            'HVIL_OBC_Req': 0,
            'HVIL_MCU_Req': 0,
            'HVIL_MCU_Sts': 0,
            'HVIL_OBC_Sts': 0,
            'BMS_Chrgr_CAN_Heartbeat': 0
        },
        'cycle_time': 100  # ms
    },
    

    
    # Get Debug Message
    'GET_DEBUG_MSG': {
        'signals': {
            'GET_DEBUG_MSG': 0
        },
        'cycle_time': 1000  # ms
    },
    
    # Battery Limits Message
    'BATTERY_LIMITS': {
        'signals': {
            'Chrg_Curr_limit': 30,
            'DisChrg_Curr_limit': -30,
            'Regen_Curr_Limit': 0,
            'Time_to_Chrg_Hrs': 0,  # Added required signal
            'Time_to_Chrg_Mins': 0  # Added required signal
        },
        'cycle_time': 100  # ms
    },
    
    # Battery Status Info Message
    'BATTERY_STS_INFO': {
        'signals': {
            'Chrg_Vlt_limit': 120,
            'Chrgr_Mode_Request': 1,
            'Battery_Curr': -300,
            'Battery_Pack_SoC': 0,  # Added required signal
            'Time_to_Chrg_Hrs': 0,  # Added required signal
            'Time_to_Chrg_Mins': 0
        },
        'cycle_time': 100  # ms
    }
}

# Legacy format for backward compatibility
# This will be populated dynamically from the DBC file
CYCLIC_CAN_MESSAGES_LEGACY = {}

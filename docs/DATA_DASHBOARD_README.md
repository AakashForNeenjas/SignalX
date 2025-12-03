# AtomX Data Dashboard - Futuristic Signal Visualization Guide

## Overview

The Data Dashboard is a sophisticated, real-time signal visualization interface that displays CAN signal values in a futuristic, visually appealing manner. It combines analog gauges, digital displays, and status indicators to provide comprehensive monitoring of system parameters.

## Key Features

### 1. **Futuristic Design**
- **Dark Theme**: Deep navy (#0a0e27) background with cyan (#00d4ff) and lime (#00ff88) accent colors
- **Gradient Backgrounds**: Smooth color gradients for depth and visual appeal
- **Custom Widgets**: Hand-crafted gauges and displays with professional styling
- **Responsive Layout**: 4-column grid layout that adapts to window size

### 2. **Multiple Visualization Modes**

#### A. **Gauge Widget** (Analog Gauges)
- **Purpose**: Display continuous analog values (voltages, currents, temperatures)
- **Features**:
  - 270° arc gauge with color-coded segments
  - Smooth needle indicator
  - Gradient coloring (Cyan → Green → Yellow → Red)
  - Min/Max labels
  - Current value display in large font
  - Signal reference from DBC configuration
  - Real-time updates with smooth animation

**Used for:**
- GridVol, GridCur (0-500V, -100-100A)
- HvVol, HvCur (High Voltage measurements)
- LvVol, LvCur (Low Voltage measurements)
- BusVol, BmsVol (Bus/Battery voltages)
- Temperature sensors (OBC, FET, DCDC, Transformer)

#### B. **Digital Display Widget**
- **Purpose**: Show numeric values with precise decimal display
- **Features**:
  - Large monospace font for clarity
  - Pink border (#ff006e) for distinction
  - Unit display (V, A, °C, etc.)
  - Signal reference tag
  - Perfect for version numbers, state values

**Used for:**
- Firmware/Hardware/Bootloader versions
- State values
- Any precise numeric display

#### C. **Status Indicator Widget**
- **Purpose**: Display system status with visual indicators
- **Features**:
  - Color-coded status (Green = OK, Yellow = Warning, Red = Error)
  - Pulsing LED indicator
  - Dynamic border coloring
  - Status text with word wrapping
  - Real-time alarm evaluation

**Used for:**
- System status and fault conditions
- Error state monitoring
- System health indicators

### 3. **Smart Signal Categorization**

The dashboard automatically categorizes signals:
- **Voltages**: All signals containing "Vol" or "Voltage"
- **Currents**: All signals containing "Cur" or "Current"
- **Temperatures**: All signals containing "Temp" or "Temperature"
- **Other**: General status and version signals

### 4. **Flexible View Modes**

Users can filter displayed signals using the view selector:
- **All Signals**: Show every configured signal
- **Voltages**: Show only voltage measurements
- **Currents**: Show only current measurements
- **Temperatures**: Show only temperature readings

### 5. **CAN Signal Integration**

Each widget is directly mapped to DBC signals defined in `CAN Configuration/signal_mapping.json`:
- Display shows the DBC signal name (e.g., `[GridVol]`)
- Real-time data flows from CAN bus to signal manager
- Automatic value updates every 500ms
- Seamless integration with Configuration tab value table

## UI Components

### Header
```
REAL-TIME SIGNAL DASHBOARD
```
Cyan (#00d4ff) text on dark background for maximum visibility.

### Control Bar
- **View Selector**: ComboBox to filter signals by category
- **Refresh Button**: Manual data refresh trigger
- **Status Indicators**: Real-time connection and update status

### Signal Widgets (4-column grid)
- Responsive grid layout that wraps automatically
- Each widget displays one CAN signal
- Smooth scrolling for large signal sets
- Consistent spacing and alignment

### Status Bar
- Current status (e.g., "Real-time Update Active")
- Last update timestamp
- Error messages if any

## Color Scheme

### Main Colors
| Color | Hex Code | Usage |
|-------|----------|-------|
| Dark Background | #0a0e27 | Main window background |
| Medium Dark | #0f3460 | Tab and panel backgrounds |
| Dark Blue | #16213e | Input fields and widget backgrounds |
| Cyan | #00d4ff | Primary accent, borders, text |
| Lime Green | #00ff88 | Success, active state, positive values |
| Pink | #ff006e | Alerts, errors, warnings |
| Orange | #ffb703 | Caution state |

### Gauge Color Gradient
- **0-60% filled**: Cyan to Green (safe operating range)
- **60-85% filled**: Yellow (caution range)
- **85-100% filled**: Red-Orange (danger range)

## Signal Mapping Configuration

The dashboard reads signal metadata from `CAN Configuration/signal_mapping.json`:

```json
{
  "dbc_signal": "GridVol",
  "ui_element": "Grid Voltage",
  "type": "value"
}
```

This defines:
- **dbc_signal**: The actual CAN signal name from DBC file
- **ui_element**: Display name in dashboard
- **type**: Data type ("value", "status", etc.)

### Adding New Signals

To add a new signal to the dashboard:

1. **Update Configuration**:
   Edit `CAN Configuration/signal_mapping.json` and add:
   ```json
   {
     "dbc_signal": "YourSignalName",
     "ui_element": "Display Label",
     "type": "value"
   }
   ```

2. **Automatic Detection**:
   - Signal name analysis for categorization
   - Widget type selection based on signal characteristics
   - Automatic min/max range assignment
   - Unit assignment based on naming conventions

3. **No Code Changes Required**:
   Dashboard auto-loads on startup, creating widgets for all configured signals

## Real-Time Data Flow

```
CAN Bus
   ↓
CANManager
   ↓
SignalManager (processes signal values)
   ↓
DataDashboard (updates widgets)
   ↓
Visual Display (500ms refresh rate)
```

### Data Update Process
1. CAN messages received from bus
2. Signal Manager decodes values using DBC
3. Signal values stored in `signal_manager.signals` dict
4. Dashboard timer triggers update (every 500ms)
5. Widgets call `set_value()` and re-paint
6. Status bar updates with timestamp

## User Interactions

### Refresh Data
Click the "Refresh Data" button to force immediate update of all values.

### View Filtering
Use the "Select View" dropdown to filter signals:
- Choose category to show only relevant signals
- Reduces visual clutter
- Easier to focus on specific measurements

### Signal Details
Hover over widget to see:
- Current exact value
- DBC signal reference
- Min/Max operating ranges

## Advanced Features

### 1. **Performance Optimization**
- Only visible widgets update (off-screen widgets skip updates)
- Efficient Qt painting with RenderHint antialiasing
- Batched signal updates every 500ms

### 2. **Error Handling**
- Graceful handling of missing signals
- Default values for disconnected sources
- Status bar error reporting
- No crashes on invalid data

### 3. **Scalability**
- Supports unlimited number of signals
- Automatic grid layout wrapping
- Scroll area for large signal sets
- Memory-efficient widget management

### 4. **Customization**
- Colors easily configurable in source code
- Widget sizes adjustable via setMinimumSize()
- Update frequency configurable (default 500ms)
- Gauge ranges editable for different scales

## Integration with AtomX Platform

### Configuration Tab
The Configuration tab displays a value table with:
- UI Element name
- Current value
- Signal type
- Linked DBC signal

### Data Tab (Dashboard)
Visual real-time representation of the same signals with:
- Gauges for continuous values
- Digital displays for precise numbers
- Status indicators for state monitoring
- Color-coded alarms and warnings

### Instrument Tab
Hardware control interface remains independent but feeds data to:
- CAN messages that update gauges
- Status indicators reflecting hardware state

## Troubleshooting

### Widgets Not Updating
1. Check `signal_mapping.json` is valid JSON
2. Verify DBC signals exist in loaded DBC file
3. Confirm CAN connection is active
4. Check SignalManager has valid reference
5. Look for errors in Application Output

### No Signals Appearing
1. Verify `signal_mapping.json` file exists
2. Confirm at least one signal mapping exists
3. Check DBC file is loaded (see Configuration tab output)
4. Restart application to reload configuration

### Incorrect Units Displayed
1. Edit signal display in DataDashboard.py `create_signal_widgets()` method
2. Add custom unit mapping for specific signals
3. Override gauge ranges for non-standard measurements

### Performance Issues
1. Reduce update frequency (increase timer interval)
2. Limit number of visible signals using view filters
3. Disable off-screen widget updates
4. Use lower resolution for very large displays

## Future Enhancements

Planned features for future versions:
- [ ] Real-time data logging to CSV
- [ ] Historical graph views (trend analysis)
- [ ] Customizable alarm thresholds
- [ ] Data export functionality
- [ ] Custom layout presets (save/load)
- [ ] Signal trending (moving average display)
- [ ] Multi-window support for multiple dashboards
- [ ] Voice alerts for critical conditions
- [ ] Mobile app connection for remote monitoring

## Technical Details

### Main Components

**GaugeWidget**
- Inherits: QWidget
- Paints: 270° arc gauge with needle
- Updates: `set_value(value)` method
- Size: Minimum 200x240 pixels

**DigitalDisplayWidget**
- Inherits: QWidget
- Paints: Large numeric display
- Updates: `set_value(value)` method
- Size: Minimum 150x120 pixels

**StatusIndicatorWidget**
- Inherits: QWidget
- Paints: Status LED and text
- Updates: `set_status(status)` method
- Size: Minimum 140x110 pixels

**DataDashboard**
- Inherits: QWidget
- Main container for all visualizations
- Manages signal loading and widget creation
- Handles periodic updates via QTimer
- Filters based on view selection

### File Structure
```
ui/
├── DataDashboard.py          (New - contains all dashboard components)
├── MainWindow.py             (Updated - integrates dashboard)
└── Dashboard.py              (Existing - Configuration tab)

CAN Configuration/
└── signal_mapping.json       (Maps DBC signals to display names)
```

## Support and Documentation

For more information:
- See `CAN Configuration/signal_mapping.json` for signal definitions
- Check DBC file contents for available signals
- Review MainWindow.py for integration code
- Examine DataDashboard.py for widget implementations

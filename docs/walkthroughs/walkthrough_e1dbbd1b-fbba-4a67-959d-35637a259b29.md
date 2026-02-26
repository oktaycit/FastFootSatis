# Walkthrough: Order Ready Notification

The order ready notification system is now functional. When an order is completed in the kitchen, the specific terminal(s) that placed that order will receive a real-time notification.

## Changes Made

### Backend: `web_server.py`
- Modified `handle_add_item` and `handle_terminal_data` to tag orders with the source `terminal_id`.
- Added a `kitchen_order_ready` event handler to process completion signals and broadcast notifications to relevant client SIDs.

### Kitchen UI: `mutfak.html`
- Updated `addOrderToGrid` to track all `terminal_id`s associated with a table's pending items.
- Updated `completeOrder` to send the table name and the list of terminal IDs back to the server when clicking "TAMAMLANDI".

### Terminal UI: `script.js`
- Added a listener for the `order_ready` event.
- Implemented `showOrderReadyNotification` which plays a notification sound and displays a success toast/alert with the message (e.g., "Masa 1 Siparişi Hazır!").

## Verification Steps

1.  **Backend Integration**: Verified that `web_server.py` correctly handles the `kitchen_order_ready` event and emits `order_ready` to specific `sid`s.
2.  **Kitchen Workflow**: Verified that the kitchen screen accumulates terminal IDs and sends them upon completion.
3.  **Terminal Feedback**: Verified that the terminal receives the socket event and triggers the visual/audio alert.

> [!TIP]
> This system is designed to notify only the terminal that placed the order, reducing unnecessary alerts for other terminals. If multiple terminals add items to the same table, all involved terminals will receive the notification when the order card is marked as complete.

---

# Walkthrough: Terminal Access Control

Terminals are now restricted from performing checkout and management operations to prevent unauthorized access.

## Changes Made

### Frontend: `script.js`
- Added role detection using URL parameters (`?role=terminal`) and `localStorage` persistence.
- Implemented `applyTerminalRestrictions` to hide payment buttons, management links, and disable payment-related JavaScript functions.
- Terminals now display "(Sipariş Terminali)" next to their ID for clarity.

### Backend: `web_server.py`
- Added server-side validation in the `finalize_payment` event to reject requests if the client sends a `role: 'terminal'` flag.
- Fixed code structure to ensure proper function separation.

## How to use
- **Main Checkout (Kasa):** Access the system normally or via `/?role=kasa`.
- **Order Terminal:** Access the system via `/?role=terminal`. This setting will persist in that browser's LocalStorage.

> [!NOTE]
> This dual approach (UI hiding + Backend validation) provides a robust way to manage multiple devices in the restaurant without requiring complex authentication.


# Real-Time Order Status Notifications

## Overview
This implementation provides real-time order status notifications to users without requiring any changes to the existing frontend code. Users will receive instant notifications when their order status changes (pending → confirmed → delivered or cancelled).

## WebSocket Endpoints

### For Users (Real-time Notifications)
```
ws://localhost:8000/ws/notifications/?email=user@example.com
```

### For Admin (Order Management)
```
ws://localhost:8000/ws/orders/
```

## Frontend Integration (No Changes Required)

The frontend can connect to the WebSocket using the user's email:

```javascript
// Example connection (add this to existing frontend if needed)
const userEmail = "user@example.com"; // Get from user context
const socket = new WebSocket(`ws://localhost:8000/ws/notifications/?email=${userEmail}`);

socket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'order_status_update') {
        const order = data.data;
        console.log(`Order #${order.order_id} status changed from ${order.previous_status} to ${order.status}`);
        
        // Show notification to user
        showNotification(`Your order #${order.order_id} is now ${order.status}`);
    }
};

function showNotification(message) {
    // Implement your notification display logic
    alert(message); // Simple example
}
```

## Message Format

When an order status changes, users receive:

```json
{
    "type": "order_status_update",
    "data": {
        "order_id": 123,
        "customer_name": "John Doe",
        "customer_email": "john@example.com",
        "status": "confirmed",
        "previous_status": "pending",
        "total": "25.99",
        "date": "2024-01-15T10:30:00Z",
        "notification_type": "status_change"
    }
}
```

## Order Status Flow

1. **pending** → Order placed, awaiting confirmation
2. **confirmed** → Order confirmed by admin
3. **delivered** → Order completed and delivered
4. **cancelled** → Order cancelled (can happen from any status)

## Testing

1. Start the Django server with ASGI support:
   ```bash
   python manage.py runserver
   ```

2. Connect to WebSocket using browser console or WebSocket client

3. Create/update orders through admin panel or API

4. Observe real-time notifications

## Implementation Details

- Uses Django Channels for WebSocket support
- User-specific channels based on email address
- Automatic signal-based broadcasting on status changes
- No database polling required
- Supports multiple concurrent user connections
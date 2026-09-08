# KisanSetu Frontend — Modular React Structure

The original single `src/main.jsx` has been split into small files for easier debugging.

## Structure

```text
src/
├── api/
│   └── api.js                 # Axios client / backend base URL
├── components/
│   ├── UI.jsx                 # Reusable Card, Pill, IconButton, UsersIcon
│   ├── Header.jsx
│   ├── BottomNav.jsx
│   ├── DesktopNav.jsx
│   └── NotificationDrawer.jsx
├── data/
│   └── centres.js              # Bihar procurement centre data
├── pages/
│   ├── Auth.jsx
│   ├── FarmerHome.jsx
│   ├── Booking.jsx
│   ├── Queue.jsx
│   ├── Payments.jsx
│   └── Operator.jsx
├── utils/
│   └── helpers.js              # date, money, location, voice and help-bot helpers
├── App.jsx                     # App/session/page routing
├── main.jsx                    # React entry point only
└── styles.css
```

## Debugging

- Login/register issue → `pages/Auth.jsx`
- Farmer home/dashboard issue → `pages/FarmerHome.jsx`
- Slot booking issue → `pages/Booking.jsx`
- Live queue issue → `pages/Queue.jsx`
- Payment/receipt issue → `pages/Payments.jsx`
- Centre/operator issue → `pages/Operator.jsx`
- API URL/request issue → `api/api.js`
- Shared UI issue → `components/UI.jsx`
- Navigation/header issue → `components/`
- Common calculations/voice → `utils/helpers.js`

Final build notes: Supabase-backed FastAPI, DB token RPC, server-side slot validation, i18n language toggle.

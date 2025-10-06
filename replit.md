# List Tracker Web App

## Overview
A minimalistic Flask-based web application for creating, managing, and sharing lists with social features. Built with MongoDB, featuring automatic alphabetical sorting, ethereal lists (restorable templates), and a clean dark/light mode interface.

## Features Implemented

### User Authentication
- Registration and login system using Flask-Login
- Password hashing with Werkzeug
- Session management with persistent cookies
- MongoDB-based user storage

### List Management
- Create lists with name, thumbnail image, tags, and visibility settings
- Two list types:
  - **Standard Lists**: Permanent item management
  - **Ethereal Lists**: Template-style lists with two modes:
    - **Check Off Mode** (default): Check items off temporarily, restore with "Uncheck All"
    - **Edit Mode** (owner only): Modify original template items permanently
- Edit list properties (name, tags, visibility, thumbnail)
- Delete lists with confirmation
- Public/private visibility toggle

### Item Management
- Add items with automatic alphabetical sorting (case-insensitive)
- Click-to-delete functionality for items
- Autocomplete suggestions from user's previous items
- Success/failure modal feedback on add operations
- Undo system for deleted items (stack-based, max 10 items)
- Ethereal list restoration to original state

### Social Features
- Browse and discover public lists
- Search lists by name
- Filter lists by tags
- Favorite/unfavorite any list (including own lists) with star icon (☆/⭐)
- Star icons on landing page and explore page for quick favoriting
- Favorited lists displayed at top of home page
- See list owner information

### UI/UX
- Dark mode (default) and light mode with toggle
- Theme preference persistence (localStorage for anonymous, DB for authenticated)
- Responsive design with TailwindCSS
- Clean, minimalistic interface
- Auto-dismissing notification modals
- Image upload with interactive cropping and compression (client-side, max 500KB)
  - Custom file picker with "Choose File" button
  - Interactive crop modal with visual rectangle overlay
  - Drag to move crop area, resize via corner handles
  - Dimmed overlay shows excluded areas (50% opacity)
  - Rectangle maintains thumbnail aspect ratio (160/300)
  - Automatic compression after cropping if needed
  - Visual feedback during processing
  - Shows final file size and crop status

## Technical Stack

### Backend
- Python 3.11
- Flask web framework
- Flask-Login for authentication
- Flask-WTF for forms and CSRF protection
- PyMongo for MongoDB interaction
- Werkzeug for password hashing
- Pillow for image processing

### Frontend
- Jinja2 templating
- TailwindCSS (CDN)
- Vanilla JavaScript
- Fetch API for AJAX calls

### Database
- MongoDB (local instance)
- Collections: users, lists, favorites, autocomplete_cache
- Proper indexing on frequently queried fields

## Project Structure
```
.
├── app.py                 # Main Flask application
├── database.py           # MongoDB database helper
├── start_mongo.sh        # MongoDB startup script
├── templates/            # Jinja2 templates
│   ├── base.html
│   ├── landing.html
│   ├── login.html
│   ├── register.html
│   ├── index.html
│   ├── create_list.html
│   ├── edit_list.html
│   ├── view_list.html
│   └── explore.html
├── static/
│   └── uploads/          # User-uploaded thumbnails
└── data/                 # MongoDB data directory
```

## Environment Variables
- `MONGO_URI`: MongoDB connection string (default: mongodb://localhost:27017/)
- `SESSION_SECRET`: Secret key for Flask sessions

## Recent Changes
- 2025-10-06: Interactive image cropping for thumbnails
  - Modal-based crop interface with visual rectangle overlay
  - Drag rectangle to reposition crop area
  - Resize rectangle via corner handles (maintains aspect ratio)
  - Dimmed overlay (50% opacity) shows excluded areas
  - Rectangle dimensions match thumbnail display aspect ratio
  - Automatic compression applied after cropping if needed
  - Cancel button to discard crop and reselect image
- 2025-10-06: Automatic image compression for thumbnails
  - Client-side image compression using Canvas API
  - Automatically resizes and compresses images over 500KB
  - Progressive quality reduction until file fits size limit
  - Visual feedback shows compression status and final file size
  - Custom file picker button prevents browser overlay issues
- 2025-10-06: Enhanced favorites functionality
  - Added star icons (☆/⭐) for favoriting/unfavoriting on landing and explore pages
  - Enabled favoriting own lists (private and public)
  - Reordered landing page to show favorites at the top
  - Simplified explore page UI with star icons instead of button text
- 2025-10-06: Improved item management UX
  - Input textbox stays focused after adding items
  - Edit Mode in ethereal lists now allows continuous item addition
  - Fixed delete buttons visibility on regular lists (all items now deletable)
- 2025-10-05: Added dual-mode system for ethereal lists
  - Check Off Mode: Temporary item checking with visual feedback
  - Edit Mode: Permanent template modification (owner only)
  - Mode toggle button with context-aware restore functionality
- 2025-10-05: Initial implementation of all MVP features
  - Complete user authentication system
  - List and item management with sorting
  - Ethereal list functionality
  - Social discovery and favorites
  - Theme toggle system
  - Image upload handling

## Architecture Notes
- All items automatically sort alphabetically on addition
- Ethereal lists store original_items snapshot for restoration
- Items have 'checked' field for check-off mode tracking
- Ethereal list modes:
  - Check Off Mode: Items displayed with checkboxes, add input hidden, restore unchecks all
  - Edit Mode: Items displayed with delete buttons, add input visible, restore resets to original_items
- Image cropping and compression flow:
  - Interactive crop modal appears on image selection
  - Canvas-based interface with draggable/resizable rectangle overlay
  - Rectangle maintains thumbnail aspect ratio (160px height / 300px width)
  - 50% opacity overlay dims excluded areas
  - Corner handles for proportional resizing
  - Mouse cursor changes based on interaction (move, resize handles)
  - Cropped image extracted via Canvas API
  - Client-side compression using HTML5 Canvas API
  - Progressive quality reduction (0.9 to 0.1) and dimension scaling (90% steps)
  - Converts all uploads to JPEG format for optimal compression
  - Server enforces 500KB max with proper error handling
- Autocomplete cache tracks user's item history with frequency
- CSRF protection enabled on all forms
- Password hashing using Werkzeug's generate_password_hash
- Session-based authentication with Flask-Login
- MongoDB indexes on email, username, list fields for performance

## Known Limitations
- Uses TailwindCSS CDN (not production-ready, should be compiled)
- Local MongoDB instance (not suitable for production deployment)
- Image uploads stored locally (should use cloud storage for production)
- No rate limiting on API endpoints
- No email verification for user registration

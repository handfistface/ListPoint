# List Point Web App

## Overview
List Point is a minimalistic Flask-based web application for creating, managing, and sharing various types of lists. It offers social features like list discovery and collaboration, robust user authentication, and a clean, responsive UI. The platform aims to provide an intuitive list-making experience supporting permanent item management and dynamic, restorable checklist templates. The business vision focuses on a streamlined list management solution with integrated social functionalities and a sustainable revenue model through subscriptions and advertising.

## User Preferences
I prefer iterative development and want to be involved in key decision-making processes. Please ask for my approval before implementing major changes or new features. I appreciate clear, concise explanations and prefer a modular, well-structured codebase. I am open to suggestions for improvements but want to maintain a focus on core functionality and user experience.

## System Architecture

### UI/UX Decisions
The application features a clean, minimalistic design with a responsive interface built using TailwindCSS, supporting both dark (default) and light modes. Navigation is streamlined, and image uploads incorporate interactive cropping, compression, and visual feedback.

### Technical Implementations
- **Authentication**: Flask-Login handles user registration, login, session management, and password hashing using Werkzeug.
- **Admin Interface**: A secure admin panel for user management (view, edit fields, manage roles/groups/admin status) and orphaned list management.
- **List Management**: Supports "Standard Lists" for permanent items and "Check Lists" as templates. Check Lists have "Check Off Mode" and "Edit Mode." Lists support alphabetical sections and manual ordering for ordered lists. All lists are public by default.
- **Item Management**: Features click-to-delete, right-click/long-press to edit, autocomplete suggestions, and an undo system for deleted items. Items can be moved between sections or to loose items.
- **List Sections**: Organize items into sections with visual distinction. Sections have their own context menu for rename and delete. Items can be added directly to sections.
- **Ordered Lists**: Allows manual item reordering via drag-and-drop, with numbering display and persistence of item order. Items can be dragged to empty sections in move mode.
- **Social Features**: Browse, search, filter public lists; favorite lists; invite collaborators with shared item management.
- **Image Handling**: Client-side image cropping and compression (up to 500KB) to JPEG.
- **Revenue System**: Integrates Google AdSense for ads and Stripe for subscription-based ad removal.
- **SEO Optimization**: Comprehensive SEO including title tags, meta descriptions, Open Graph, Twitter Cards, Schema.org, XML sitemap, robots.txt, and descriptive alt text.

### System Design Choices
- Items are alphabetically sorted within sections (which are also alphabetically sorted) or manually ordered if "Ordered Lists" is enabled. Loose items appear at the bottom.
- Check lists store `original_items` for restoration and `checked` status.
- Sections are stored as a `section` field on items.
- Image cropping uses a canvas-based interface with touch/mouse support, maintaining a 160px height / 300px width aspect ratio.
- Autocomplete caches user item history.
- Context menus (right-click/long-press) for items and sections position dynamically within the viewport and match the theme.
- Clipboard API is used for copy functionality.
- Custom-themed edit modals support keyboard shortcuts.
- Text selection is disabled on list items to prevent interference with custom context menus.
- CSRF protection is enabled.
- MongoDB indexes are used for performance.
- All lists are public (`is_public=True`).
- **List Cloning & Genealogy**: Lists track parent-child relationships. Deleting a parent reassigns children to a grandparent or creates an orphaned copy managed by admins.
- **Permission System**: `can_manage_list()` helper function manages list access based on ownership, collaboration, or admin privileges for orphaned lists.

## External Dependencies
- **Database**: MongoDB (remote via MongoDB Atlas)
- **Payment Processing**: Stripe
- **Advertising**: Google AdSense
- **Backend Framework**: Flask
- **Authentication**: Flask-Login
- **Forms**: Flask-WTF
- **MongoDB Driver**: PyMongo
- **Password Hashing**: Werkzeug
- **Image Processing (Python)**: Pillow
- **Frontend Styling**: TailwindCSS (CDN)
- **Client-side Scripting**: Vanilla JavaScript, Fetch API
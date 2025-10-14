# List Point Web App

## Recent Changes
- **October 14, 2025**: 
  - Fixed undo functionality bug where deleted items were not being restored to the list without a page reload. Created missing `/api/lists/<list_id>` JSON API endpoint that returns list data with items.
  - Fixed context menu bug where right-click/long-press dialog was appearing during regular list interactions. Added event listener guard to prevent duplicate listeners from being attached when list is rebuilt.
  - Fixed edit item modal lingering after item edit. Changed implementation to fetch updated list data and rebuild the list asynchronously, ensuring modal closes properly and items are correctly ordered within sections without page reload.
  - Fixed undo modal to show only unique items (most recent occurrence of each) with proper index handling for accurate restoration.
  - Added user-select: none styling to undo button to prevent text selection on right-click/long-press.

## Overview
List Point is a minimalistic Flask-based web application designed for creating, managing, and sharing various types of lists. It incorporates social features, such as list discovery and collaboration, alongside robust user authentication and a clean, responsive user interface. The platform aims to provide a flexible and intuitive list-making experience, supporting both permanent item management and dynamic, restorable checklist templates. The business vision is to offer a streamlined list management solution with integrated social functionalities and a sustainable revenue model through subscriptions and advertising.

## User Preferences
I prefer iterative development and want to be involved in key decision-making processes. Please ask for my approval before implementing major changes or new features. I appreciate clear, concise explanations and prefer a modular, well-structured codebase. I am open to suggestions for improvements but want to maintain a focus on core functionality and user experience.

## System Architecture

### UI/UX Decisions
The application features a clean, minimalistic design with a responsive interface built using TailwindCSS. It supports both dark (default) and light modes, with theme preferences persisted. Navigation is streamlined, grouping list management controls for intuitive access. Image uploads incorporate interactive cropping, compression, and visual feedback for an enhanced user experience.

### Technical Implementations
- **Authentication**: Flask-Login handles user registration, login, session management, and password hashing using Werkzeug.
- **Admin Interface**: Secure admin panel for user management. Admins can view all users (excluding password hashes), edit user fields (except passwords), manage roles and groups, and toggle admin status. All admin routes are protected with authorization checks. Access to the admin panel is shown conditionally in the navigation menu based on the user's admin status.
- **List Management**: Supports "Standard Lists" for permanent items and "Check Lists" which act as templates. Check Lists have "Check Off Mode" for temporary checking and "Edit Mode" for permanent template modification. Items are automatically sorted alphabetically. Lists now support sections for better organization (implemented October 14, 2025).
- **Item Management**: Includes features like click-to-delete, right-click/long-press to edit items, autocomplete suggestions, and an undo system for deleted items.
- **List Sections**: Comprehensive section management system allows users to organize items within lists. Sections are created by right-clicking/long-pressing items and moving them into named sections. Sections appear alphabetically at the top with a striped visual pattern, while loose (unsectioned) items appear at the bottom with a separator. Section headers have their own context menu for rename and delete operations. Each section has a dedicated add button with autocomplete positioned above the input to prevent mobile keyboard interference (implemented October 14, 2025).
- **Social Features**: Users can browse, search, and filter public lists, favorite lists, and invite collaborators. Collaborative lists allow shared item management (add, delete, adjust quantity) for both owners and collaborators.
- **Image Handling**: Client-side image cropping and compression (up to 500KB) with a custom file picker and visual feedback. Images are converted to JPEG for optimal compression.
- **Revenue System**: Integrates Google AdSense for ads and Stripe for subscription-based ad removal. Ad display logic intelligently handles ad loading and ensures no whitespace is shown if ads fail to load.
- **SEO Optimization**: Comprehensive SEO implementation including optimized title tags, unique meta descriptions for all pages, Open Graph tags for social sharing, Twitter Card tags, Schema.org structured data (WebApplication), XML sitemap (accessible at /sitemap.xml), robots.txt configuration, and descriptive alt text for all images. Targets keywords: "online list maker", "shared list app", "collaborative task lists", "free list organizer".

### Feature Specifications
- **User Accounts**: Registration, login, session management.
- **Admin Management**: Admin panel for viewing and managing all users, editing user fields, managing roles and groups. Admin access is role-based with secure route protection. Admins can also manage orphaned lists (lists owned by "None" user) created when parent lists are deleted.
- **List Creation**: Name, thumbnail, tags. All lists are public by default (as of October 11, 2025).
- **List Types**: Standard (permanent) and Check Lists (template-based with two modes).
- **Item Operations**: Add, delete, edit (via right-click or long-press), check/uncheck (for Check Lists), undo, organize into sections.
- **Section Operations**: Create sections from items, rename sections, delete sections (with confirmation), add items directly to sections with autocomplete support.
- **Discovery**: Browse, search, filter lists by tags. Infinite scroll implementation loads 10 lists at a time, sorted by most recently updated, with automatic preloading when user scrolls through 5 items (implemented October 11, 2025). Last updated time is displayed on all list cards showing when the list was last modified.
- **Last Updated Time Display**: All list cards (on index and explore pages) display the last update time in a user-friendly format: relative time for recent updates (e.g., "2h ago", "5m ago") and absolute date/time (MM/DD/YYYY HH:MM) for updates older than 7 days. The timestamp updates automatically when items are added, removed, quantity is adjusted, or the list is edited (implemented October 11, 2025).
- **Collaboration**: Invite/remove collaborators, shared list access and full item editing capabilities (add, delete, adjust quantity) for collaborators.
- **Favorites**: Mark/unmark lists as favorites for quick access.
- **List Cloning**: Users can clone any accessible list to create their own copy with all items. Cloned lists track their parent (original) list and display genealogy information. Clone count shown with 🌿 emoji on list cards. Parents display links to their children with owner information in a modal.
- **Theming**: Dark/Light mode toggle with persistence.
- **Image Uploads**: Interactive cropping, compression, aspect ratio control (160/300).
- **Footer Pages**: About Us page describing the platform's mission, features, and solo developer background. Contact Us page with email contact information (kirschnerjohn10@gmail.com).

### System Design Choices
- All items are automatically sorted alphabetically upon addition. When sections exist, items within each section are sorted alphabetically, and sections themselves are sorted alphabetically at the top of the list, with loose items appearing at the bottom.
- Check lists store an `original_items` snapshot for restoration.
- `items` in check lists have a `checked` field and an optional `section` field for organization.
- **List Sections Storage**: Sections are stored as a field (`section`) on each item rather than as separate entities. Items with a `section` field are grouped and displayed together with visual distinction (striped pattern). Loose items (section=null) appear at the bottom with a horizontal separator.
- Image cropping uses a canvas-based interface, maintaining a 160px height / 300px width aspect ratio, with touch and mouse event support.
- Autocomplete cache tracks user's item history for suggestions. When items are edited, the old autocomplete entry is replaced with the new text (not duplicated).
- Context menus appear on right-click (desktop) or long-press 500ms (mobile) with haptic feedback. Item context menu offers "Copy Text", "Edit Item", and "Create Section" options. Section headers have their own context menu offering "Rename Section" and "Delete Section" options.
- Context menu automatically positions itself to stay within viewport boundaries and matches the site's theme.
- Copy functionality uses Clipboard API with fallback for older browsers.
- Edit modal is a custom themed component matching the site's dark/light theme with keyboard shortcuts (Enter to save, Escape to cancel).
- List items have text selection disabled (user-select: none) to prevent system dialogs from interfering with custom context menu.
- CSRF protection is enabled on all forms.
- MongoDB indexes are used for performance on frequently queried fields.
- **List Visibility**: All lists are enforced as public. The visibility UI control is hidden from users, and backend code ensures `is_public=True` for all list creation and editing operations. This was implemented on October 11, 2025 to simplify the platform and promote list sharing.
- **List Cloning & Genealogy**: Lists track parent-child relationships via `parent_id` and `clone_count` fields. When a parent list is deleted, children are reassigned to their grandparent. If no grandparent exists, an orphan copy owned by "None" user is created to preserve genealogy. Admins have special permissions to manage orphaned lists (implemented October 12, 2025).
- **Permission System**: Custom `can_manage_list()` helper function checks if a user can manage a list based on ownership, collaboration status, or admin privileges for orphaned lists. This ensures admins can maintain orphaned lists while regular users cannot access them.

## External Dependencies
- **Database**: MongoDB (remote instance via MongoDB Atlas)
- **Payment Processing**: Stripe (for subscriptions and payment management)
- **Advertising**: Google AdSense (for displaying ads)
- **Backend Framework**: Flask
- **Authentication**: Flask-Login
- **Forms**: Flask-WTF
- **MongoDB Driver**: PyMongo
- **Password Hashing**: Werkzeug
- **Image Processing (Python)**: Pillow
- **Frontend Styling**: TailwindCSS (CDN)
- **Client-side Scripting**: Vanilla JavaScript, Fetch API (for AJAX)
# Loading Screen Setup Instructions

## Overview
A full-page video loading screen that displays your logo animation on the first page visit. The screen:
- Plays automatically when the app loads (first visit only)
- Auto-dismisses when the video ends
- Includes a "Skip" button for users to dismiss early
- Uses localStorage to remember that the user has seen it (won't show again)
- Shows on all pages app-wide

## Files Created

1. **loading-screen.css** - Styling for the overlay and video container
2. **loading-screen.js** - JavaScript logic for managing the loading screen behavior
3. **videos/** - Directory for storing your video file

## Setup Instructions

### Step 1: Add Your Video File
Place your video file here as: `logo-animation.mp4`

**Location:** `static/heatmap/videos/logo-animation.mp4`

**Supported Formats:**
- MP4 (recommended) - `.mp4`
- WebM - `.webm` 
- Ogg - `.ogv`

If using a different format/name, update the `src` in `templates/base_app.html` line 30.

### Step 2: Video Specifications

**Recommended specifications:**
- **Duration:** 3-5 seconds (ideal for a loading screen)
- **Resolution:** 1920x1080 or higher
- **Format:** MP4 (H.264 codec)
- **File Size:** < 5MB (for fast loading)
- **Audio:** Muted (no audio on load screens)

### Step 3: Testing

To test the loading screen:
1. Open the app in an incognito/private browser window (this bypasses the localStorage cache)
2. Or use browser DevTools → Application → Storage → Local Storage → delete the `netsense_loading_shown` entry
3. Refresh the page to see the loading screen again

### Step 4: Customization Options

#### Change Skip Button Text
Edit in `static/heatmap/js/loading-screen.js` - modify the button HTML in `templates/base_app.html`

#### Adjust Timing
- Change transition speed in `static/heatmap/css/loading-screen.css` (default: 0.3s)
- Adjust visibility delay in `static/heatmap/js/loading-screen.js` (default: 100ms)

#### Modify Colors
Edit `static/heatmap/css/loading-screen.css`:
- Background color: Change `background-color: #000` (currently black)
- Button styling: Modify `#loading-screen-skip` styles

#### Show on Every Visit
In `static/heatmap/js/loading-screen.js`, comment out or remove these lines:
```javascript
// Mark as shown in localStorage
localStorage.setItem(this.storageKey, 'true');
```

#### Customize Skip Button Position
Edit `.loading-screen-skip` in `static/heatmap/css/loading-screen.css`:
```css
bottom: 40px;  /* Distance from bottom */
right: 40px;   /* Distance from right */
```

## Browser Compatibility

Works on all modern browsers:
- Chrome/Edge: ✓
- Firefox: ✓
- Safari: ✓
- Mobile browsers: ✓

## Accessibility Features

- Skip button is properly labeled with `aria-label`
- Video is muted to prevent autofocus issues
- Proper z-index (9999) to appear above all content
- Smooth transitions for less jarring experience

## Troubleshooting

**Loading screen not showing:**
- Check that video file is placed at `static/heatmap/videos/logo-animation.mp4`
- Clear browser cache and localStorage
- Check browser console for errors
- Ensure JavaScript is enabled

**Video not playing:**
- Verify the video file exists at the correct path
- Try a different video format (WebM or Ogg)
- Check video codec compatibility

**Skip button not working:**
- Check browser console for JavaScript errors
- Ensure loading-screen.js is loaded

## Advanced: Reset Loading Screen for Testing

In browser DevTools console, run:
```javascript
new LoadingScreen().reset()
```

This will clear the localStorage and reload the page to show the loading screen again.

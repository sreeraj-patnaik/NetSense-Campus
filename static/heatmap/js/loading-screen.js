/**
 * Loading Screen Manager
 * Displays logo animation video on home page every time, or first visit on other pages
 */

class LoadingScreen {
    constructor() {
        this.loadingOverlay = document.getElementById('loading-screen-overlay');
        this.video = document.getElementById('loading-screen-video');
        this.skipBtn = document.getElementById('loading-screen-skip');
        this.storageKey = 'netsense_loading_shown';
        
        if (!this.loadingOverlay) {
            console.log('LoadingScreen: Overlay element not found');
            return;
        }
        
        this.init();
    }

    init() {
        const isHomePage = this.checkIfHomePage();
        const isDashboard = this.checkIfDashboard();
        console.log('LoadingScreen: isHomePage =', isHomePage, 'isDashboard =', isDashboard);
        console.log('LoadingScreen: current path =', window.location.pathname);
        
        // Always show on home or dashboard page. For other pages, show only once per browser session.
        if (!isHomePage && !isDashboard && this.hasShownBefore()) {
            console.log('LoadingScreen: Already shown in this session, dismissing');
            this.dismiss();
            return;
        }

        // Set up event listeners
        this.video.addEventListener('ended', () => {
            console.log('LoadingScreen: Video ended, dismissing');
            this.dismiss();
        });
        
        this.video.addEventListener('error', (e) => {
            console.error('LoadingScreen: Video error:', e);
            this.dismiss();
        });
        
        this.skipBtn.addEventListener('click', () => {
            console.log('LoadingScreen: Skip clicked');
            this.dismiss();
        });

        this.unmuteBtn = document.getElementById('loading-screen-unmute');
        if (this.unmuteBtn) {
            this.unmuteBtn.addEventListener('click', () => {
                console.log('LoadingScreen: Unmute clicked');
                this.video.muted = false;
                this.video.volume = 1;
                this.unmuteBtn.classList.add('hidden');
            });
        }

        // Add slight delay before showing to ensure smooth page load
        setTimeout(() => {
            console.log('LoadingScreen: Showing overlay and playing video');
            this.loadingOverlay.classList.add('show');
            document.body.classList.add('loading-screen-visible');
            if (this.unmuteBtn) {
                this.unmuteBtn.classList.remove('hidden');
            }
            
            // Ensure video is ready and play
            this.video.play().then(() => {
                console.log('LoadingScreen: Video play started');
            }).catch(err => {
                console.error('LoadingScreen: Error playing video:', err);
                if (this.unmuteBtn) {
                    this.unmuteBtn.classList.remove('hidden');
                }
                this.video.muted = true;
            });
        }, 100);
    }

    dismiss() {
        console.log('LoadingScreen: Dismissing');
        this.loadingOverlay.classList.remove('show');
        this.loadingOverlay.classList.add('dismissed');
        document.body.classList.remove('loading-screen-visible');
        this.video.pause();
        this.video.currentTime = 0;
        
        // Mark as shown in sessionStorage (only for non-home pages)
        if (!this.checkIfHomePage()) {
            console.log('LoadingScreen: Marking as shown in sessionStorage');
            sessionStorage.setItem(this.storageKey, 'true');
        }
        
        // Remove overlay from DOM after animation completes
        setTimeout(() => {
            this.loadingOverlay.style.display = 'none';
        }, 500);
    }

    hasShownBefore() {
        return sessionStorage.getItem(this.storageKey) === 'true';
    }

    checkIfHomePage() {
        const currentPath = window.location.pathname;
        const isHome = currentPath === '/' || 
                       currentPath === '/home' || 
                       currentPath === '/landing' ||
                       currentPath === '/index';
        
        console.log('LoadingScreen: Checking if home page. Path:', currentPath, 'IsHome:', isHome);
        return isHome;
    }

    checkIfDashboard() {
        const currentPath = window.location.pathname;
        const isDashboard = currentPath === '/dashboard/' ||
                            currentPath === '/dashboard';
        console.log('LoadingScreen: Checking if dashboard page. Path:', currentPath, 'IsDashboard:', isDashboard);
        return isDashboard;
    }

    // Method to force show (useful for testing)
    reset() {
        console.log('LoadingScreen: Resetting');
        localStorage.removeItem(this.storageKey);
        location.reload();
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('LoadingScreen: DOM ready, initializing');
        new LoadingScreen();
    });
} else {
    console.log('LoadingScreen: DOM already loaded, initializing');
    new LoadingScreen();
}

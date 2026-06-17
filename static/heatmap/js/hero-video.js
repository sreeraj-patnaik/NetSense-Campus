document.addEventListener('DOMContentLoaded', function () {
  const vid = document.getElementById('heroVideo');
  if (!vid) return;

  // Try to play programmatically (some browsers block autoplay even when muted)
  const playAttempt = vid.play();
  if (playAttempt !== undefined) {
    playAttempt.catch(err => {
      console.warn('Hero video autoplay blocked:', err);
      showPlayOverlay();
    });
  }

  function showPlayOverlay() {
    // create a minimal play button overlay to let user start the video
    const wrap = document.querySelector('.marketing-hero');
    if (!wrap) return;
    // avoid adding twice
    if (wrap.querySelector('.hero-play-overlay')) return;

    const btn = document.createElement('button');
    btn.className = 'hero-play-overlay';
    btn.innerText = 'Play';
    Object.assign(btn.style, {
      position: 'absolute',
      left: '50%',
      top: '50%',
      transform: 'translate(-50%,-50%)',
      padding: '0.8rem 1.2rem',
      borderRadius: '999px',
      border: 'none',
      background: 'linear-gradient(135deg,#6366f1,#4f46e5)',
      color: '#fff',
      zIndex: 9999,
      cursor: 'pointer',
      fontWeight: 700,
      boxShadow: '0 8px 30px rgba(0,0,0,.4)'
    });

    btn.addEventListener('click', () => {
      vid.play().then(() => {
        btn.remove();
      }).catch(e => console.warn('Play failed:', e));
    });

    wrap.appendChild(btn);
  }
});

// Additional listeners to update UI when playback state changes
document.addEventListener('DOMContentLoaded', function () {
  const vid = document.getElementById('heroVideo');
  const wrap = document.querySelector('.marketing-hero');
  if (!vid || !wrap) return;

  function updateState() {
    if (vid.paused || vid.readyState === 0) {
      wrap.classList.add('no-video-playing');
      showPlayOverlay();
    } else {
      wrap.classList.remove('no-video-playing');
      const existing = wrap.querySelector('.hero-play-overlay');
      if (existing) existing.remove();
    }
  }

  // Try to set an initial state after a short delay to allow autoplay attempt
  setTimeout(updateState, 200);

  vid.addEventListener('playing', updateState);
  vid.addEventListener('play', updateState);
  vid.addEventListener('pause', updateState);
  vid.addEventListener('ended', updateState);
});

// Fallback: start video on first user interaction (click/tap) to satisfy autoplay policies
(function enableGesturePlay(){
  const vid = document.getElementById('heroVideo');
  if (!vid) return;
  function onFirstInteraction() {
    vid.play().catch(()=>{});
    document.removeEventListener('pointerdown', onFirstInteraction, true);
  }
  document.addEventListener('pointerdown', onFirstInteraction, true);
})();

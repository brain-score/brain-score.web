// loading-animation.js
const LoadingAnimation = {
  // Set to true to disable the loading animation (for performance testing)
  DISABLED: true,

  fallbackTimeout: null,
  _raf: null,
  _progress: 0,
  _autoTarget: 90,       // auto mode won't cross this; complete() takes it to 100
  _autoSpeed: 0.025,     // base speed; tweak for slower/faster fill
  _lastTs: 0,
  _isVisible: false,

  show() {
    if (this.DISABLED) return;

    const overlay = document.getElementById('loading-overlay');
    if (!overlay || this._isVisible) return;

    overlay.style.display = 'flex';
    this._isVisible = true;
    this.setProgress(0);

    // Smooth CSS transition if your SASS doesn't already do this
    const bar = document.getElementById('loader-progress-bar');
    if (bar && !bar.style.transition) {
      bar.style.transition = 'width 150ms ease';
    }

    window.addEventListener('beforeunload', this.handleCancel);

    // start auto progress (asymptotic to _autoTarget)
    this._lastTs = performance.now();
    this._startAutoProgress();

    // Safety fallback (hide if something goes very wrong)
    this.fallbackTimeout = setTimeout(() => {
      console.warn('Loading animation fallback timeout reached - hiding animation');
      this.complete();
    }, 15000); // 15s feels less jarring than 10s for cold loads
  },

  hide() {
    const overlay = document.getElementById('loading-overlay');
    if (!overlay) return;

    overlay.style.display = 'none';
    this._isVisible = false;
    window.removeEventListener('beforeunload', this.handleCancel);

    // clear timers
    if (this.fallbackTimeout) { clearTimeout(this.fallbackTimeout); this.fallbackTimeout = null; }
    if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
  },

  handleCancel() { LoadingAnimation.hide(); },

  // ---- progress helpers ----
  setProgress(pct) {
    const clamped = Math.max(0, Math.min(100, pct));
    this._progress = clamped;

    const bar = document.getElementById('loader-progress-bar');
    const label = document.getElementById('loader-progress-label');
    if (bar) bar.style.width = clamped + '%';
    if (label) label.textContent = Math.round(clamped) + '%';
  },

  // Optional: gently nudge progress upward by a delta (won’t exceed 99 without complete())
  bump(delta = 3) {
    const cap = Math.min(99, this._autoTarget); // avoid hitting 100 from bumps
    this.setProgress(Math.min(cap, this._progress + Math.max(0.5, delta)));
  },

  // animate to a target over durationMs with easeOutQuad; returns a Promise
  _animateTo(target, durationMs = 400) {
    return new Promise(resolve => {
      const start = performance.now();
      const from = this._progress;

      const tick = (now) => {
        const t = Math.min(1, (now - start) / durationMs);
        const eased = 1 - (1 - t) * (1 - t);
        this.setProgress(from + (target - from) * eased);
        if (t < 1) {
          this._raf = requestAnimationFrame(tick);
        } else {
          resolve();
        }
      };
      this._raf = requestAnimationFrame(tick);
    });
  },

  _startAutoProgress() {
    const step = (now) => {
      if (!this._isVisible) return;

      const dt = Math.max(0, now - this._lastTs);
      this._lastTs = now;

      // Distance to target controls speed (slows down as it approaches target)
      const dist = Math.max(0, this._autoTarget - this._progress);

      // Small randomized multiplier to make it feel organic; frame-rate independent
      const jitter = 0.9 + Math.random() * 0.2;

      // Exponential easing toward target
      const increment = dist * this._autoSpeed * (dt / 16.67) * jitter;

      // Never stall completely; tiny floor helps during long waits
      const floor = 0.03;
      const next = this._progress + Math.max(floor, increment);

      this.setProgress(Math.min(this._autoTarget, next));

      this._raf = requestAnimationFrame(step);
    };

    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = requestAnimationFrame(step);
  },

  // Public: call when your app/data is fully ready OR wait for window 'load' below
  async complete() {
    if (!this._isVisible) return;

    // Ensure any auto rAF loop doesn't fight this final animation
    if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }

    // Smoothly finish to 100, then hide shortly after
    await this._animateTo(100, 350);
    setTimeout(() => this.hide(), 10);
  }
};

// Hide on BFCache restore, just in case
window.addEventListener('pageshow', (e) => { if (e.persisted) LoadingAnimation.hide(); });
window.addEventListener('popstate', () => LoadingAnimation.hide());


/**
 * Custom Image Comparison Slider
 * A lightweight, custom implementation for before/after image comparisons
 */

class ImageComparison {
  constructor(container) {
    this.container = container;
    this.slider = container.querySelector('.comparison-slider');
    this.resize = container.querySelector('.comparison-resize');
    this.isDragging = false;
    
    this.init();
  }
  
  init() {
    if (!this.slider || !this.resize) {
      console.warn('Image comparison slider elements not found');
      return;
    }
    
    // Add event listeners
    this.slider.addEventListener('mousedown', this.handleMouseDown.bind(this));
    this.slider.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
    
    // Prevent text selection and image dragging
    this.container.addEventListener('selectstart', e => e.preventDefault());
    this.container.addEventListener('dragstart', e => e.preventDefault());
    
    // Add keyboard support
    this.slider.setAttribute('tabindex', '0');
    this.slider.setAttribute('role', 'slider');
    this.slider.setAttribute('aria-label', 'Image comparison slider');
    this.slider.setAttribute('aria-valuemin', '0');
    this.slider.setAttribute('aria-valuemax', '100');
    this.slider.setAttribute('aria-valuenow', '50');
    
    this.slider.addEventListener('keydown', this.handleKeyDown.bind(this));
    
    // Setup image sizing
    this.setupImages();
    
    // Set initial position
    this.updatePosition(50);
  }
  
  setupImages() {
    const afterImg = this.container.querySelector('> img');
    const beforeImg = this.resize.querySelector('img');
    
    if (afterImg && beforeImg) {
      // Wait for the base image to load to get proper dimensions
      if (afterImg.complete) {
        this.syncImageSizes();
      } else {
        afterImg.addEventListener('load', () => this.syncImageSizes());
      }
      
      // Also handle window resize
      window.addEventListener('resize', () => this.syncImageSizes());
    }
  }
  
  syncImageSizes() {
    const afterImg = this.container.querySelector('> img');
    const beforeImg = this.resize.querySelector('img');
    
    if (afterImg && beforeImg) {
      // Get the actual rendered dimensions of the after image
      const rect = afterImg.getBoundingClientRect();
      
      // Set CSS custom properties for the before image to match exactly
      this.container.style.setProperty('--container-width', rect.width + 'px');
      this.container.style.setProperty('--container-height', rect.height + 'px');
      
      // Also set the resize container height to match
      this.resize.style.height = rect.height + 'px';
    }
  }
  
  handleMouseDown(e) {
    e.preventDefault();
    this.isDragging = true;
    
    document.addEventListener('mousemove', this.handleMouseMove.bind(this));
    document.addEventListener('mouseup', this.handleMouseUp.bind(this));
    
    this.container.style.cursor = 'ew-resize';
  }
  
  handleTouchStart(e) {
    e.preventDefault();
    this.isDragging = true;
    
    document.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
    document.addEventListener('touchend', this.handleTouchEnd.bind(this));
  }
  
  handleMouseMove(e) {
    if (!this.isDragging) return;
    
    const rect = this.container.getBoundingClientRect();
    const percentage = ((e.clientX - rect.left) / rect.width) * 100;
    this.updatePosition(percentage);
  }
  
  handleTouchMove(e) {
    if (!this.isDragging) return;
    e.preventDefault();
    
    const touch = e.touches[0];
    const rect = this.container.getBoundingClientRect();
    const percentage = ((touch.clientX - rect.left) / rect.width) * 100;
    this.updatePosition(percentage);
  }
  
  handleMouseUp() {
    this.isDragging = false;
    this.container.style.cursor = '';
    
    document.removeEventListener('mousemove', this.handleMouseMove.bind(this));
    document.removeEventListener('mouseup', this.handleMouseUp.bind(this));
  }
  
  handleTouchEnd() {
    this.isDragging = false;
    
    document.removeEventListener('touchmove', this.handleTouchMove.bind(this));
    document.removeEventListener('touchend', this.handleTouchEnd.bind(this));
  }
  
  handleKeyDown(e) {
    let percentage = parseFloat(this.slider.getAttribute('aria-valuenow'));
    
    switch(e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        percentage = Math.max(0, percentage - 5);
        break;
      case 'ArrowRight':
        e.preventDefault();
        percentage = Math.min(100, percentage + 5);
        break;
      case 'Home':
        e.preventDefault();
        percentage = 0;
        break;
      case 'End':
        e.preventDefault();
        percentage = 100;
        break;
      default:
        return;
    }
    
    this.updatePosition(percentage);
  }
  
  updatePosition(percentage) {
    // Clamp percentage between 0 and 100
    percentage = Math.max(0, Math.min(100, percentage));
    
    this.resize.style.width = percentage + '%';
    this.slider.style.left = percentage + '%';
    this.slider.setAttribute('aria-valuenow', percentage.toFixed(1));
  }
  
  // Public method to set position programmatically
  setPosition(percentage) {
    this.updatePosition(percentage);
  }
}

// Auto-initialize all comparison containers when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  const containers = document.querySelectorAll('.comparison-container');
  containers.forEach(container => {
    new ImageComparison(container);
  });
});

// Export for manual initialization if needed
window.ImageComparison = ImageComparison;

document.addEventListener("DOMContentLoaded", function () {
  console.log("DOM fully loaded and parsed");

  // Function to detect mobile devices using the user agent
  function isMobileDevice() {
    return /Mobi|Android|iPhone|iPad|iPod/.test(navigator.userAgent);
  }

  // Detect if the user is on a mobile device
  if (isMobileDevice()) {
    console.log("Mobile device detected");

    const modal = document.getElementById('mobile-warning-modal');
    const mainContent = document.querySelector('main');
    const dismissBtn = document.getElementById('dismiss-modal-btn');

    // Show the modal and blur the background
    modal.classList.remove('is-hidden');
    mainContent.classList.add('is-blurred');

    console.log("Modal displayed, background blurred");

    // Remove blur and hide modal when the user clicks the button
    dismissBtn.addEventListener('click', function () {
      modal.classList.add('is-hidden');
      mainContent.classList.remove('is-blurred');
      console.log("Modal dismissed, blur removed");
    });
  } else {
    console.log("Desktop or non-mobile device detected, no modal");
  }
});
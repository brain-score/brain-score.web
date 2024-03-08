// Adds the logic for a popup to display announcements:

document.addEventListener('DOMContentLoaded', () => {
  const popup = document.getElementById('popup-notification');
  const closeBtn = popup.querySelector('.modal-close');
  const bodyContent = document.querySelector('body');

  setTimeout(() => {
    popup.style.display = 'block'; // Make the popup block to start transition
    setTimeout(() => popup.classList.add('is-active'), 10); // A slight delay to ensure transition occurs
    bodyContent.classList.add('blur-background');

    closeBtn.addEventListener('click', () => {
      popup.classList.remove('is-active');
      setTimeout(() => popup.style.display = 'none', 500); // Wait for fade-out to finish
      bodyContent.classList.remove('blur-background');
    });

    setTimeout(() => {
      popup.classList.remove('is-active');
      setTimeout(() => {
        popup.style.display = 'none';
        bodyContent.classList.remove('blur-background');
      }, 500); // Wait for fade-out to finish
    }, 15000); // Display for 15 seconds
  }, 5000); // Wait 5 seconds before showing
});
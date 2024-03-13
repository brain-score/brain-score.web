document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.toggle-button').forEach(button => {
    button.addEventListener('click', () => {
      const content = button.nextElementSibling;
      const isExpanded = button.getAttribute('aria-expanded') === 'true';
      button.setAttribute('aria-expanded', !isExpanded);
      content.classList.toggle('is-hidden', isExpanded);
      content.classList.toggle('is-shown', !isExpanded);
      // Assuming you're using Font Awesome 5, updating class for rotation
      button.querySelector('.fas').classList.toggle('fa-rotate-180', !isExpanded);
    });
  });
});
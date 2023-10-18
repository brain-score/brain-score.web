window.onload = function() {
    const errorMessage = document.getElementById('wrong-password');
    if (errorMessage) {
        setTimeout(() => {
            errorMessage.classList.add('fade-out');
        }, 5000); // Show the message for 5 seconds, then start the fade
    }
};
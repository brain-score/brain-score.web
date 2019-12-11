var button = document.getElementById('upload_button');
var input  = document.getElementById('id_zip_file');

// Making input invisible, but leaving shown for graceful degradation
input.style.display = 'none';
button.style.display = 'initial';

button.addEventListener('click', function (e) {
    e.preventDefault();
    
    input.click();
});

input.addEventListener('change', function () {
   button.innerText = this.value; 
});
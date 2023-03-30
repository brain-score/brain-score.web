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
    const ext = this.value.match(/\.([^\.]+)$/)[1];
    switch (ext) {
    case 'zip':
      button.innerText = this.value;
      break;
    default:
      alert('Please submit a .zip file.');
      this.value = "Click here to select file"
  }
});
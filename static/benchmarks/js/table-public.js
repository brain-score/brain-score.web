$(document).ready(function(){
    var checkedCheckboxes = {};

    $('input').click(function(){

    var checkedCheckboxes = {};
        $('input').each(function(){

            console.log($(this).is(':checked'));
            checkedCheckboxes[$(this).val()] = $(this).is(':checked')
        });

    // Now we have an array
    console.log('JS Array: ');
    console.log(checkedCheckboxes);

    // Convert array to standard Javascript Object Literal
    var checkedCheckboxesObject = $.extend({}, checkedCheckboxes);
    console.log('JS Object: ');
    console.log(checkedCheckboxesObject);

    // Convert Object Literal to JSON
    var checkedCheckboxesJSON = JSON.stringify(checkedCheckboxesObject);
    console.log('JSON: ');
    console.log(checkedCheckboxesJSON);

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    var csrftoken = getCookie('csrftoken');
    console.log(csrftoken);
    function csrfSafeMethod(method) {
        // these HTTP methods do not require CSRF protection
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }

    $.ajaxSetup({
        crossDomain: false, // obviates need for sameOrigin test
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type)) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });
    $.ajax({
            type: "POST",
            url: "../public-ajax/",
            dataType: 'json',
            contentType: 'json',
            data: JSON.stringify(checkedCheckboxesJSON),
            success: function(msg){
                console.log(msg);
            },
        });
    });
});
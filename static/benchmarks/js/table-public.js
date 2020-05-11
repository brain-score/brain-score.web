$(document).ready(function(){
    var checkedCheckboxes = {};

    $('input').click(function(){

    var checkedCheckboxes = {};
        $('input').each(function(){

            checkedCheckboxes[$(this).val()] = $(this).is(':checked')
        });

    // Convert array to standard Javascript Object Literal
    var checkedCheckboxesObject = $.extend({}, checkedCheckboxes);
    
    // Convert Object Literal to JSON
    var checkedCheckboxesJSON = JSON.stringify(checkedCheckboxesObject);
    
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
        });
    });
});
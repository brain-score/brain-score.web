// adapted from http://codetheory.in/change-active-state-links-sticky-navigation-scroll/

var sections = $('section')
    , nav = $('.navbar-item')
    , nav_height = nav.outerHeight();

$(window).on('scroll', function () {
    var cur_pos = $(this).scrollTop();

    sections.each(function() {
        var top = $(this).offset().top - nav_height,
            bottom = top + $(this).outerHeight();

        if (cur_pos >= top && cur_pos <= bottom) {
            nav.removeClass('is-active');
            nav.filter('[href$="#'+$(this).attr('id')+'"]').addClass('is-active');
        }
    });
});

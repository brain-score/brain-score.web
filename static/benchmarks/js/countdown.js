// adapted from https://stackoverflow.com/a/25702998/2225200

const date = '2024-06-30';

$('#countdown_competition2024').countdown(date).on('update.countdown', function (event) {
    let formatted_html = '<span>' + (event.offset.months * 30 + event.offset.daysToMonth) + '</span>'
        + event.strftime(''
            + ' day%!d '
            + '<span>%H</span>h '
            + '<span>%M</span>m '
            + '<span>%S</span>s');
    $(this).html(formatted_html);
});

document.addEventListener('mdl-componentupgraded', function(e) {
    if (typeof e.target.MaterialLayout !== 'undefined') {
        var head = document.getElementsByTagName('head')[0];
        var script = document.createElement('script');
        script.type = 'text/javascript';
        script.src = '/static/django_tinymce/init_tinymce.js';
        head.appendChild(script);
    }
});

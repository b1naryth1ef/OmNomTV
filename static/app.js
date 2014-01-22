window.CACHE = {
    templates: {}
} || window.CACHE

function getTemplate(name) {
    return window.CACHE.templates[name]
}

function loadTemplate(name) {
    $.ajax("/api/template", {
        data: {
            "name": name
        },
        async: false,
        success: function (data) {
            if (data.error) {
                console.log('loadTemplate has an error: '+data.error)
            }

            if (data.content) {
                window.CACHE.templates[name] = _.template(data.content)
            }
        }
    })
}

function selectSeason(show, season) {
    show = show || window.CACHE.show;
    season = season || window.CACHE.season;
    window.CACHE.show = show;
    window.CACHE.season = season;
    $.ajax("/api/season/"+show+"/"+season+"/get", {
        success: function(data) {
            if (data.season) {
                data = getTemplate("season.html")({
                    season: data.season
                })
                $("#active-season-episode-list").html(data)
                $(".pop").popover({
                    trigger: "hover"
                })
            }
        }
    })
}

function onLoad() {
    loadTemplate("show.html")
    loadTemplate("season.html")

    // Add event: Load season
    $("#shows").delegate(".season-select", "click", function (e) {
        e.stopImmediatePropagation();
        selectSeason($(this).attr("show-id"), $(this).attr("season-id"))

    })

    $("#shows").delegate(".episode-action", "click", function (e) {
        e.stopImmediatePropagation();
        parent = $($(this).parent())
        $.ajax("/api/episode/get", {
            data: {
                "show": parent.attr("show"),
                "episode": parent.attr("episode"),
                "season": parent.attr("season")
            },
            success: function(data) {
                if (data.success) {
                    selectSeason()
                }

                if (data.error) {
                    alert(data.error)
                }
            }
        })
    })

    // First we load all the shows
    $.ajax("/api/show/list", {
        success: function(data) {
            if (data.shows) {
                _.each(data.shows, function (el, i) {
                    data = getTemplate("show.html")({show: el})
                    $("#shows").append(data)
                })
            }
        }
    })
}

$(document).ready(onLoad)

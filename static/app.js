window.CACHE = {
    templates: {}
};

function getTemplate(name) {
    return window.CACHE.templates[name] || loadTemplate(name);
}

function loadTemplate(name) {
    $.ajax("/api/template", {
        data: {
            "name": name
        },
        async: false,
        success: function (data) {
            if (data.error) {
                console.log('loadTemplate has an error: '+data.error);
            }

            if (data.content) {
                window.CACHE.templates[name] = _.template(data.content);
            }
        }
    });
    return getTemplate(name);
}

Error = {
    create: function (msg, type, clear) {
        type = type || "error";
        clear = clear || true;
        var data = getTemplate("error.html")({
            msg: msg,
            type: type,
        });

        if (clear) {
            Error.clear()
        }

        $(".errors").append(data)
    },

    clear: function () {
        $(".errors").html("")
    }
}

function selectSeason(show, season) {
    // Commence derp code
    window.CACHE.show = show = (show || window.CACHE.show);
    window.CACHE.season = season = (season || window.CACHE.season);

    $.ajax("/api/season/"+show+"/"+season+"/get", {
        success: function(data) {
            if (data.season) {
                data = getTemplate("season.html")({
                    season: data.season
                });
                $("#active-season-episode-list-"+show).html(data);
                $(".pop").popover({
                    trigger: "click"
                });
            }
        }
    });
}

var CONFIG = {
    autoSearch: false
};

function handleSearchResults(data) {
    $(".search-loader").hide();
    if (data.error) {
        Error.create(data.error)
        return;
    }
    $("#results").html("");
    _.each(data.results, function (el, i) {
        data = getTemplate("search.html")({
            show: el
        });
        $("#results").append(data);
    });
}

function loadShows() {
    // First we load all the shows
    $("#shows").html("");
    $("#results").html("");
    $.ajax("/api/show/list", {
        success: function(data) {
            if (data.shows) {
                _.each(data.shows, function (el, i) {
                    data = getTemplate("show.html")({show: el});
                    $("#shows").append(data);
                });
            }
        }
    });
}

function onLoad() {
    loadTemplate("show.html");
    loadTemplate("season.html");
    loadTemplate("search.html");
    loadTemplate("error.html");

    // Add event: Load season
    $("#shows").delegate(".season-select", "click", function (e) {
        e.stopImmediatePropagation();
        // Select a new season for this show
        selectSeason($(this).attr("show-id"), $(this).attr("season-id"));
        // Hide the menu
        $(".dropdown-toggle-"+$(this).attr("show-id")).dropdown('toggle');
    });

    $("#shows").delegate(".show-delete", "click", function (e) {
        $.ajax("/api/show/delete", {
            data: {
                "show": $(this).attr("show-id")
            },
            success: function(data) {
                if (data.error) {
                    Error.create(data.error)
                    return;
                }
                loadShows();
            }
        });
    });

    $("#results").delegate(".search-add", "click", function (e) {
        e.stopImmediatePropagation();
        $.ajax("/api/show/add", {
            data: {
                "show": $(this).parent().attr("id")
            },
            success: function (data) {
                if (data.error) {
                    Error.create(data.error);
                    return;
                }
                loadShows();
                $(".search-info").fadeOut();
            }
        });
    });

    $("#shows").delegate(".episode-action", "click", function (e) {
        e.stopImmediatePropagation();
        var parent = $($(this).parent());
        var action = $(this).attr("act");
        $.ajax("/api/episode/"+action, {
            data: {
                "show": parent.attr("show"),
                "episode": parent.attr("episode"),
                "season": parent.attr("season")
            },
            success: function(data) {
                if (data.success) {
                    selectSeason();
                }

                if (data.error) {
                    Error.create(data.error)
                }
            }
        });
    });

    // Search on enter
    $("#search").keydown(function (e) {
        e.stopImmediatePropagation();
        if (e.keyCode == 13 || (CONFIG.autoSearch && $(this).val().length >= 5)) {
            if ($(this).val() === "") {
                $("#results").html("");
                $(".search-info").fadeOut();
                return;
            }
            $(".search-info").fadeIn();
            $(".search-loader").show();
            $.ajax("/api/search", {
                data: {
                    "query": $(this).val()
                },
                success: handleSearchResults
            });
        }
    });



    loadShows();
}

$(document).ready(onLoad);


Show = {
    id: instance id,
    poster: image url,
    name: show name,
    num_seasons: total # of seasons,
    seasons: [... season numbers],
    state: {
        have: %,
        getting: %,
        other: %,
        unavail: %
    }
}

Season = {
    id: small int,
    episodes: [... Episode{}]
}

Episode = {
    id: small int,
    season: small int,
    name: episode name,
    desc: episode desc,
    airdate: day of airing,
    state: ['none', 'have', 'getting', 'unavail'],
    prog: % done,
    path: some url,
    fname: file name
}
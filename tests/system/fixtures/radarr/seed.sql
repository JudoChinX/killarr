INSERT OR REPLACE INTO RootFolders (Id, Path) VALUES (1, '/tmp/media');
INSERT OR REPLACE INTO Tags (Id, Label) VALUES (1, 'test-tag');

INSERT OR REPLACE INTO MovieMetadata (
    Id, TmdbId, Images, Title, SortTitle, CleanTitle,
    OriginalTitle, CleanOriginalTitle, Status, Runtime,
    Recommendations, OriginalLanguage, Year, Ratings, Genres, Keywords
) VALUES (
    1, 99000001, '[]', 'Test Movie 01', 'test movie 01', 'testmovie01',
    'Test Movie 01', 'testmovie01', 3, 120,
    '[]', 1, 2020, '{}', '[]', '[]'
);

INSERT OR REPLACE INTO Movies (
    Id, Path, Monitored, QualityProfileId, MovieFileId, MinimumAvailability, MovieMetadataId
) VALUES (1, '/tmp/media/test-movie-01', 1, 1, 0, 1, 1);

INSERT OR REPLACE INTO DownloadClients (
    Id, Enable, Name, Implementation, Settings, ConfigContract,
    Priority, RemoveCompletedDownloads, RemoveFailedDownloads
) VALUES (
    1, 1, 'FakeSAB', 'Sabnzbd',
    '{"host":"fakesab","port":8080,"useSsl":false,"urlBase":"","apiKey":"killarr-test","movieCategory":"radarr","recentMoviePriority":-100,"olderMoviePriority":-100}',
    'SabnzbdSettings',
    1, 1, 0
);

INSERT OR REPLACE INTO History (
    Id, MovieId, SourceTitle, Date, Quality, Data, EventType, DownloadId, Languages
) VALUES (
    1, 1,
    'Test.Movie.01.2020.WEB-DL',
    '2026-01-01T00:00:00Z',
    '{"quality":3,"revision":{"version":1,"real":0,"isRepack":false},"customFormatScore":0,"qualityDetectionSource":"name"}',
    '{"downloadClient":"FakeSAB","downloadClientName":"FakeSAB","releaseGroup":"","protocol":"usenet","releaseType":"unknown"}',
    1,
    'killarr-test-radarr-001',
    '[1]'
);

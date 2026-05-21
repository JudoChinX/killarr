INSERT OR REPLACE INTO RootFolders (Id, Path) VALUES (1, '/tmp/media');
INSERT OR REPLACE INTO Tags (Id, Label) VALUES (1, 'test-tag');

INSERT OR REPLACE INTO Series (
    Id, TvdbId, TvRageId, Title, CleanTitle, Status, Images,
    Path, Monitored, SeasonFolder, Runtime, SeriesType,
    UseSceneNumbering, TvMazeId, OriginalLanguage
) VALUES (
    1, 99000001, 0, 'Test Series', 'testseries', 1, '[]',
    '/tmp/media/test-series', 1, 1, 60, 0, 0, 0, 1
);

INSERT OR REPLACE INTO Episodes (
    Id, SeriesId, SeasonNumber, EpisodeNumber,
    UnverifiedSceneNumbering, Runtime, Monitored, AirDateUtc, Title
) VALUES (
    1, 1, 1, 1, 0, 60, 1, '2026-01-01T00:00:00Z', 'Test Episode 01'
);

INSERT OR REPLACE INTO DownloadClients (
    Id, Enable, Name, Implementation, Settings, ConfigContract,
    Priority, RemoveCompletedDownloads, RemoveFailedDownloads
) VALUES (
    1, 1, 'FakeSAB', 'Sabnzbd',
    '{"host":"fakesab","port":8080,"useSsl":false,"urlBase":"","apiKey":"killarr-test","tvCategory":"sonarr","recentTvPriority":-100,"olderTvPriority":-100}',
    'SabnzbdSettings',
    1, 1, 0
);

INSERT OR REPLACE INTO History (
    Id, EpisodeId, SeriesId, SourceTitle, Date, Quality, Data, EventType, DownloadId, Languages
) VALUES (
    1, 1, 1,
    'Test.Series.S01E01.WEB-DL',
    '2026-01-01T00:00:00Z',
    '{"quality":3,"revision":{"version":1,"real":0,"isRepack":false},"customFormatScore":0,"qualityDetectionSource":"name"}',
    '{"downloadClient":"FakeSAB","downloadClientName":"FakeSAB","releaseGroup":"","protocol":"usenet","releaseType":"unknown"}',
    1,
    'killarr-test-sonarr-001',
    '[1]'
);

INSERT OR REPLACE INTO RootFolders (Id, Path) VALUES (1, '/tmp/media');

INSERT OR REPLACE INTO Tags (Id, Label) VALUES (1, 'test-tag');

INSERT OR REPLACE INTO Series (
    Id, TvdbId, Title, TitleSlug, CleanTitle, Status, Images,
    Path, Monitored, QualityProfileId, Runtime, UseSceneNumbering,
    Seasons, Ratings, OriginalLanguage, MonitorNewItems, SeriesType
) VALUES (
    1, 10000001, 'Test Performer', 'test-performer', 'testperformer', 1, '[]',
    '/tmp/media/test-performer', 1, 1, 30, 0,
    '[]', '{}', 1, 0, 0
);

INSERT OR REPLACE INTO Episodes (
    Id, Monitored, SeriesId, SeasonNumber, Title, Runtime, EpisodeFileId, AirDate, AirDateUtc
) VALUES (
    1, 1, 1, 1, 'Test Scene 01', 30, 0, '2024-01-15', '2024-01-15T00:00:00Z'
);

INSERT OR REPLACE INTO DownloadClients (
    Id, Enable, Name, Implementation, Settings, ConfigContract,
    Priority, RemoveCompletedDownloads, RemoveFailedDownloads
) VALUES (
    1, 1, 'FakeSAB', 'Sabnzbd',
    '{"host":"fakesab","port":8080,"useSsl":false,"urlBase":"","apiKey":"killarr-test","tvCategory":"whisparr_v2","recentTvPriority":-100,"olderTvPriority":-100}',
    'SabnzbdSettings',
    1, 1, 0
);

INSERT OR REPLACE INTO History (
    Id, EpisodeId, SeriesId, SourceTitle, Date, Quality, Data, EventType, DownloadId, Languages
) VALUES (
    1, 1, 1,
    'Test.Performer.Scene.01.WEB-DL',
    '2026-01-01T00:00:00Z',
    '{"quality":3,"revision":{"version":1,"real":0,"isRepack":false},"customFormatScore":0,"qualityDetectionSource":"name"}',
    '{"downloadClient":"FakeSAB","downloadClientName":"FakeSAB","releaseGroup":"","protocol":"usenet","releaseType":"unknown"}',
    1,
    'killarr-test-whisparr-v2-001',
    '[1]'
);

INSERT OR REPLACE INTO RootFolders (Id, Path) VALUES (1, '/tmp/media');

INSERT OR REPLACE INTO Tags (Id, Label) VALUES (1, 'test-tag');

INSERT OR REPLACE INTO MovieMetadata (
    Id, ForeignId, MetadataSource, Images, Title, SortTitle, CleanTitle,
    OriginalLanguage, Status, Runtime, ReleaseDate, Year, Ratings, Genres,
    Recommendations, Credits, ItemType, StudioTitle
) VALUES (
    1, 'scene-001', 0, '[]', 'Test Scene 01', 'test scene 01', 'testscene01',
    1, 3, 30, '2024-01-15', 2024, '{}', '[]',
    '[]', '[]', 0, 'Test Studio'
);

INSERT OR REPLACE INTO Movies (
    Id, Path, Monitored, QualityProfileId, MovieFileId, MovieMetadataId
) VALUES (1, '/tmp/media/test-scene-01', 1, 1, 0, 1);

INSERT OR REPLACE INTO DownloadClients (
    Id, Enable, Name, Implementation, Settings, ConfigContract,
    Priority, RemoveCompletedDownloads, RemoveFailedDownloads
) VALUES (
    1, 1, 'FakeSAB', 'Sabnzbd',
    '{"host":"fakesab","port":8080,"useSsl":false,"urlBase":"","apiKey":"killarr-test","movieCategory":"whisparr_v3","recentMoviePriority":-100,"olderMoviePriority":-100}',
    'SabnzbdSettings',
    1, 1, 0
);

INSERT OR REPLACE INTO History (
    Id, MovieId, SourceTitle, Date, Quality, Data, EventType, DownloadId, Languages
) VALUES (
    1, 1,
    'Test.Scene.01.2024.WEB-DL',
    '2026-01-01T00:00:00Z',
    '{"quality":3,"revision":{"version":1,"real":0,"isRepack":false},"customFormatScore":0,"qualityDetectionSource":"name"}',
    '{"downloadClient":"FakeSAB","downloadClientName":"FakeSAB","releaseGroup":"","protocol":"usenet","releaseType":"unknown"}',
    1,
    'killarr-test-whisparr-v3-001',
    '[1]'
);

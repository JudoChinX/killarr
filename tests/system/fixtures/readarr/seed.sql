INSERT OR REPLACE INTO RootFolders (Id, Path, Name, DefaultMetadataProfileId, DefaultQualityProfileId, DefaultMonitorOption, DefaultTags, IsCalibreLibrary, DefaultNewItemMonitorOption)
VALUES (1, '/tmp/media', 'docker-test', 1, 1, 0, '[]', 0, 0);

INSERT OR REPLACE INTO Tags (Id, Label) VALUES (1, 'test-tag');

INSERT OR REPLACE INTO AuthorMetadata (Id, ForeignAuthorId, TitleSlug, Name, Status, Images, Aliases, SortName, NameLastFirst, SortNameLastFirst)
VALUES (1, '00000000-0000-0000-0000-000000000001', 'test-author-01', 'Test Author 01', 1, '[]', '[]', 'test author 01', 'Test Author 01', 'Author 01, Test');

INSERT OR REPLACE INTO Authors (Id, CleanName, Path, Monitored, QualityProfileId, MetadataProfileId, AuthorMetadataId, MonitorNewItems)
VALUES (1, 'testauthor01', '/tmp/media/test-author-01', 1, 1, 1, 1, 0);

INSERT OR REPLACE INTO Books (Id, AuthorMetadataId, ForeignBookId, TitleSlug, Title, CleanTitle, Monitored, AnyEditionOk, ReleaseDate, Links, Genres, Ratings, RelatedBooks)
VALUES (1, 1, '00000000-0000-0000-0000-000000000101', 'test-book-01', 'Test Book 01', 'testbook01', 1, 1, '2020-01-01 00:00:00', '[]', '[]', '{}', '[]');

INSERT OR REPLACE INTO Editions (Id, BookId, ForeignEditionId, Title, TitleSlug, Images, Monitored, ManualAdd)
VALUES (1, 1, '00000000-0000-0000-0001-000000000101', 'Test Book 01', 'test-book-01-edition', '[]', 1, 0);

INSERT OR REPLACE INTO DownloadClients (
    Id, Enable, Name, Implementation, Settings, ConfigContract,
    Priority, RemoveCompletedDownloads, RemoveFailedDownloads
) VALUES (
    1, 1, 'FakeSAB', 'Sabnzbd',
    '{"host":"fakesab","port":8080,"useSsl":false,"urlBase":"","apiKey":"killarr-test","musicCategory":"readarr","recentTvPriority":-100,"olderTvPriority":-100}',
    'SabnzbdSettings',
    1, 1, 0
);

INSERT OR REPLACE INTO History (
    Id, SourceTitle, Date, Quality, Data, EventType, DownloadId, AuthorId, BookId
) VALUES (
    1,
    'Test.Author.01-Test.Book.01.WEB',
    '2026-01-01T00:00:00Z',
    '{"quality":3,"revision":{"version":1,"real":0,"isRepack":false},"customFormatScore":0,"qualityDetectionSource":"name"}',
    '{"downloadClient":"FakeSAB","downloadClientName":"FakeSAB","releaseGroup":"","protocol":"usenet","releaseType":"unknown"}',
    1,
    'killarr-test-readarr-001',
    1, 1
);

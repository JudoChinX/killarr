INSERT OR REPLACE INTO RootFolders (Id, Path, Name, DefaultMetadataProfileId, DefaultQualityProfileId)
VALUES (1, '/tmp/media', 'docker-test', 1, 1);
INSERT OR REPLACE INTO Tags (Id, Label) VALUES (1, 'test-tag');

INSERT OR REPLACE INTO ArtistMetadata (
    Id, ForeignArtistId, Name, Status, Images, Aliases, OldForeignArtistIds
) VALUES (
    1, '00000000-0000-0000-0000-000000000099', 'Test Artist', 1, '[]', '[]', '[]'
);

INSERT OR REPLACE INTO Artists (
    Id, CleanName, Path, Monitored, QualityProfileId, MetadataProfileId, ArtistMetadataId, MonitorNewItems
) VALUES (1, 'testartist', '/tmp/media/test-artist', 1, 1, 1, 1, 0);

INSERT OR REPLACE INTO Albums (
    Id, ForeignAlbumId, Title, CleanTitle, Images, Monitored,
    AlbumType, ArtistMetadataId, AnyReleaseOk, OldForeignAlbumIds, ReleaseDate
) VALUES (
    1, '00000000-0000-0000-0000-000000000001',
    'Test Album 01', 'testalbum01', '[]', 1,
    'Album', 1, 1, '[]', '2020-01-01 00:00:00'
);

INSERT OR REPLACE INTO AlbumReleases (
    Id, ForeignReleaseId, AlbumId, Title, Status, Duration, Monitored, OldForeignReleaseIds
) VALUES (
    1, '00000000-0000-0000-0001-000000000001',
    1, 'Test Album 01', 'Official', 300000, 1, '[]'
);

INSERT OR REPLACE INTO Tracks (
    Id, ForeignTrackId, Explicit, Duration, MediumNumber,
    AbsoluteTrackNumber, ForeignRecordingId, AlbumReleaseId, ArtistMetadataId
) VALUES (
    1, '00000000-0000-0000-0001-000000010001',
    0, 240000, 1, 1,
    '00000000-0000-0001-0001-000000000001',
    1, 1
);

INSERT OR REPLACE INTO DownloadClients (
    Id, Enable, Name, Implementation, Settings, ConfigContract,
    Priority, RemoveCompletedDownloads, RemoveFailedDownloads
) VALUES (
    1, 1, 'FakeSAB', 'Sabnzbd',
    '{"host":"fakesab","port":8080,"useSsl":false,"urlBase":"","apiKey":"killarr-test","musicCategory":"lidarr","recentMusicPriority":-100,"olderMusicPriority":-100}',
    'SabnzbdSettings',
    1, 1, 0
);

INSERT OR REPLACE INTO History (
    Id, ArtistId, AlbumId, TrackId, SourceTitle, Date, Quality, Data, EventType, DownloadId
) VALUES (
    1, 1, 1, 1,
    'Test.Artist-Test.Album.01.WEB',
    '2026-01-01T00:00:00Z',
    '{"quality":1,"revision":{"version":1,"real":0,"isRepack":false},"customFormatScore":0,"qualityDetectionSource":"name"}',
    '{"downloadClient":"FakeSAB","downloadClientName":"FakeSAB","releaseGroup":"","protocol":"usenet"}',
    1,
    'killarr-test-lidarr-001'
);

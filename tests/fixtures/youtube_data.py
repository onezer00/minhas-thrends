"""
Fixtures com dados de exemplo do YouTube para testes.
"""

YOUTUBE_TRENDING_RESPONSE = {
    "kind": "youtube#videoListResponse",
    "etag": "example_etag",
    "items": [
        {
            "kind": "youtube#video",
            "etag": "item_etag_1",
            "id": "video123",
            "snippet": {
                "publishedAt": "2023-01-15T10:00:00Z",
                "channelId": "UC123456789",
                "title": "Vídeo de Teste 1",
                "description": "Esta é a descrição do vídeo de teste 1 #python #programação",
                "thumbnails": {
                    "default": {
                        "url": "https://i.ytimg.com/vi/video123/default.jpg",
                        "width": 120,
                        "height": 90
                    },
                    "high": {
                        "url": "https://i.ytimg.com/vi/video123/hqdefault.jpg",
                        "width": 480,
                        "height": 360
                    }
                },
                "channelTitle": "Canal de Teste",
                "tags": ["python", "programação", "tutorial"],
                "categoryId": "28",
                "liveBroadcastContent": "none",
                "defaultLanguage": "pt-BR",
                "localized": {
                    "title": "Vídeo de Teste 1",
                    "description": "Esta é a descrição do vídeo de teste 1 #python #programação"
                },
                "defaultAudioLanguage": "pt-BR"
            },
            "statistics": {
                "viewCount": "10000",
                "likeCount": "1000",
                "favoriteCount": "0",
                "commentCount": "500"
            }
        },
        {
            "kind": "youtube#video",
            "etag": "item_etag_2",
            "id": "video456",
            "snippet": {
                "publishedAt": "2023-01-16T11:00:00Z",
                "channelId": "UC987654321",
                "title": "Vídeo de Teste 2",
                "description": "Esta é a descrição do vídeo de teste 2 #games #entretenimento",
                "thumbnails": {
                    "default": {
                        "url": "https://i.ytimg.com/vi/video456/default.jpg",
                        "width": 120,
                        "height": 90
                    },
                    "high": {
                        "url": "https://i.ytimg.com/vi/video456/hqdefault.jpg",
                        "width": 480,
                        "height": 360
                    }
                },
                "channelTitle": "Outro Canal",
                "tags": ["games", "entretenimento", "gameplay"],
                "categoryId": "20",
                "liveBroadcastContent": "none",
                "defaultLanguage": "pt-BR",
                "localized": {
                    "title": "Vídeo de Teste 2",
                    "description": "Esta é a descrição do vídeo de teste 2 #games #entretenimento"
                },
                "defaultAudioLanguage": "pt-BR"
            },
            "statistics": {
                "viewCount": "20000",
                "likeCount": "2000",
                "favoriteCount": "0",
                "commentCount": "800"
            }
        }
    ],
    "nextPageToken": "next_page_token",
    "pageInfo": {
        "totalResults": 2,
        "resultsPerPage": 2
    }
} 
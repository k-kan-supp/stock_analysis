-- ────────────────────────────────────────────
-- 業種マスタ シードデータ (東証33業種)
-- ────────────────────────────────────────────
INSERT INTO industry_master (industry_code, industry_name_ja, industry_name_en, sector_code, sector_name_ja, sector_name_en) VALUES
-- 製造業 (sector_code = M)
('01', '水産・農林業',     'Fishery, Agriculture & Forestry',    'M', '製造業', 'Manufacturing'),
('02', '鉱業',             'Mining',                              'M', '製造業', 'Manufacturing'),
('03', '建設業',           'Construction',                        'M', '製造業', 'Manufacturing'),
('04', '食料品',           'Foods',                               'M', '製造業', 'Manufacturing'),
('05', '繊維製品',         'Textiles & Apparels',                 'M', '製造業', 'Manufacturing'),
('06', 'パルプ・紙',       'Pulp & Paper',                        'M', '製造業', 'Manufacturing'),
('07', '化学',             'Chemicals',                           'M', '製造業', 'Manufacturing'),
('08', '医薬品',           'Pharmaceutical',                      'M', '製造業', 'Manufacturing'),
('09', '石油・石炭製品',   'Oil & Coal Products',                 'M', '製造業', 'Manufacturing'),
('10', 'ゴム製品',         'Rubber Products',                     'M', '製造業', 'Manufacturing'),
('11', 'ガラス・土石製品', 'Glass & Ceramics Products',           'M', '製造業', 'Manufacturing'),
('12', '鉄鋼',             'Iron & Steel',                        'M', '製造業', 'Manufacturing'),
('13', '非鉄金属',         'Nonferrous Metals',                   'M', '製造業', 'Manufacturing'),
('14', '金属製品',         'Metal Products',                      'M', '製造業', 'Manufacturing'),
('15', '機械',             'Machinery',                           'M', '製造業', 'Manufacturing'),
('16', '電気機器',         'Electric Appliances',                 'M', '製造業', 'Manufacturing'),
('17', '輸送用機器',       'Transportation Equipment',            'M', '製造業', 'Manufacturing'),
('18', '精密機器',         'Precision Instruments',               'M', '製造業', 'Manufacturing'),
('19', 'その他製品',       'Other Products',                      'M', '製造業', 'Manufacturing'),
-- 非製造業 (sector_code = N)
('20', '電気・ガス業',     'Electric Power & Gas',                'N', '非製造業', 'Non-Manufacturing'),
('21', '陸運業',           'Land Transportation',                 'N', '非製造業', 'Non-Manufacturing'),
('22', '海運業',           'Marine Transportation',               'N', '非製造業', 'Non-Manufacturing'),
('23', '空運業',           'Air Transportation',                  'N', '非製造業', 'Non-Manufacturing'),
('24', '倉庫・運輸関連',   'Warehousing & Harbor Transportation', 'N', '非製造業', 'Non-Manufacturing'),
('25', '情報・通信業',     'Information & Communication',         'N', '非製造業', 'Non-Manufacturing'),
('26', '卸売業',           'Wholesale Trade',                     'N', '非製造業', 'Non-Manufacturing'),
('27', '小売業',           'Retail Trade',                        'N', '非製造業', 'Non-Manufacturing'),
('28', '銀行業',           'Banks',                               'N', '非製造業', 'Non-Manufacturing'),
('29', '証券・商品先物取引','Securities & Commodity Futures',      'N', '非製造業', 'Non-Manufacturing'),
('30', '保険業',           'Insurance',                           'N', '非製造業', 'Non-Manufacturing'),
('31', 'その他金融業',     'Other Financing Business',            'N', '非製造業', 'Non-Manufacturing'),
('32', '不動産業',         'Real Estate',                         'N', '非製造業', 'Non-Manufacturing'),
('33', 'サービス業',       'Services',                            'N', '非製造業', 'Non-Manufacturing');


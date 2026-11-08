/* S2B Hỏi Đáp — DỮ LIỆU GIẢ cho prototype (trừ ngày thành lập ProPTIT 09/10/2011). */
(function () {
  var CLUBS = {
    ProPTIT: { k: 'pro', cls: 'club--pro', label: 'ProPTIT' },
    Multimedia: { k: 'mm', cls: 'club--mm', label: 'Multimedia' },
    GCC: { k: 'gcc', cls: 'club--gcc', label: 'GCC' },
    S2B: { k: 's2b', cls: 'club--s2b', label: 'S2B' }
  };
  function club(n) { return CLUBS[n] || CLUBS.S2B; }
  function norm(s) { return String(s || '').toLowerCase().replace(/đ/g, 'd').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim(); }

  var ICON = {
    check: 'M20 6 9 17l-5-5', x: 'M18 6 6 18M6 6l12 12', send: 'M12 19V5M5 12l7-7 7 7', plus: 'M12 5v14M5 12h14',
    menu: 'M4 6h16M4 12h16M4 18h16', sidebar: 'M3 5h18v14H3zM9 5v14', copy: 'M9 9h10v10H9zM5 15V5h10',
    up: 'M7 11v9H4v-9h3zM7 11l4-8c1.5 0 2.5 1 2.2 2.6L12.8 9H19a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 17.8 20H7',
    down: 'M17 13V4h3v9h-3zM17 13l-4 8c-1.5 0-2.5-1-2.2-2.6L11.2 15H5a2 2 0 0 1-2-2.3l1.2-7A2 2 0 0 1 6.2 4H17',
    book: 'M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5zM4 19a2 2 0 0 1 2-2h13',
    flow: 'M4 5h6v5H4zM14 14h6v5h-6zM10 7.5h2a2 2 0 0 1 2 2V14',
    sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
    moon: 'M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z',
    chevL: 'M15 18l-6-6 6-6', chevR: 'M9 18l6-6-6-6', chevD: 'M6 9l6 6 6-6', chevU: 'M18 15l-6-6-6 6',
    more: 'M5 12h.01M12 12h.01M19 12h.01',
    info: 'M12 8h.01M11 12h1v5h1M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
    alert: 'M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
    wifiOff: 'M2 8.8a15 15 0 0 1 4-2.4M22 8.8a15 15 0 0 0-6.5-3.4M5 12.9a10 10 0 0 1 3-1.8M19 12.9a10 10 0 0 0-3.5-2.2M8.5 16.4a5 5 0 0 1 7 0M12 20h.01M2 2l20 20',
    refresh: 'M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5',
    search: 'M21 21l-4.3-4.3M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0z', layers: 'M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5',
    bars: 'M5 20V10M12 20V4M19 20v-7', spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z',
    help: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01',
    trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3', pencil: 'M4 20h4L19 9l-4-4L4 16v4zM13 7l4 4',
    arrowR: 'M5 12h14M13 6l6 6-6 6', sortUp: 'M12 19V5M6 11l6-6 6 6', sortDown: 'M12 5v14M6 13l6 6 6-6',
    stop: 'M7 7h10v10H7z'
  };
  var STEPS = [
    { label: 'Hiểu câu hỏi', icon: 'help' }, { label: 'Tìm tài liệu', icon: 'search' },
    { label: 'Xếp hạng', icon: 'bars' }, { label: 'Soạn câu trả lời', icon: 'spark' }
  ];

  function C(n, id, club_, topic, text, score) { return { n: n, id: id, club: club_, topic: topic, text: text, score: score }; }

  var SC = {
    founding: {
      q: 'CLB Lập Trình PTIT thành lập khi nào?', filter: 'ProPTIT',
      rewritten: 'CLB Lập Trình PTIT (ProPTIT) được thành lập khi nào?',
      expansions: [{ from: 'ProPTIT', to: 'CLB Lập Trình PTIT' }],
      answer: 'CLB Lập Trình PTIT được thành lập ngày 09/10/2011.[1] Sau khi thành lập, CLB sinh hoạt theo các ban chuyên môn và có hoạt động đào tạo định kỳ cho thành viên mới.[2]',
      citations: [
        C(1, 12, 'ProPTIT', 'Lịch sử', 'CLB Lập Trình PTIT (ProPTIT) được thành lập ngày «09/10/2011» tại Học viện Công nghệ Bưu chính Viễn thông. Từ một nhóm nhỏ yêu thích lập trình, CLB phát triển thành môi trường học tập và thực hành dành cho sinh viên.', 0.91),
        C(2, 13, 'ProPTIT', 'Hoạt động', '[Dữ liệu giả] ProPTIT tổ chức các buổi đào tạo định kỳ theo «ban chuyên môn», kèm dự án thực tế để thành viên mới làm quen với quy trình làm việc nhóm.', 0.78),
        C(3, 1, 'S2B', 'Giới thiệu', '[Dữ liệu giả] S2B là cộng đồng sinh viên gồm ba câu lạc bộ thuộc Học viện, cùng chia sẻ thông tin tuyển thành viên và các hoạt động chung.', 0.64)
      ],
      stages: [620, 41, 540, 639], llm: 2, tokens: { 'in': 1830, out: 96 }, cost: 0.0021, cache: false, latency: 1840
    },
    nodau: {
      q: 'clb dpt tuyen thanh vien thang may', filter: 'Multimedia',
      rewritten: 'CLB Multimedia (đa phương tiện) tuyển thành viên tháng mấy?',
      expansions: [{ from: 'dpt', to: 'đa phương tiện' }, { from: 'clb', to: 'câu lạc bộ' }],
      answer: 'CLB Multimedia thường mở đơn đăng ký thành viên vào tháng 9 đầu năm học.[1] Kết quả và lịch phỏng vấn được thông báo qua kênh chính thức của CLB.[2]',
      citations: [
        C(1, 47, 'Multimedia', 'Tuyển thành viên', '[Dữ liệu giả] Đợt tuyển thành viên của CLB Multimedia mở đơn đăng ký vào «tháng 9», ngay sau khi sinh viên khóa mới nhập học và kết thúc tuần sinh hoạt công dân.', 0.93),
        C(2, 52, 'Multimedia', 'Quy trình', '[Dữ liệu giả] Sau khi nộp hồ sơ, ứng viên nhận «lịch phỏng vấn» qua kênh chính thức và theo dõi kết quả trên trang thông tin của CLB.', 0.81),
        C(3, 3, 'S2B', 'Thông báo', '[Dữ liệu giả] Các CLB thuộc S2B đăng thông báo tuyển thành viên song song để sinh viên mới dễ so sánh và lựa chọn.', 0.66)
      ],
      stages: [700, 38, 512, 580], llm: 2, tokens: { 'in': 1904, out: 88 }, cost: 0.0022, cache: false, latency: 1830
    },
    compare: {
      q: 'So sánh cách tuyển thành viên của ProPTIT và GCC', filter: null,
      rewritten: 'So sánh quy trình tuyển thành viên giữa CLB Lập Trình PTIT (ProPTIT) và CLB Nhà Sáng Tạo Game (GCC)',
      expansions: [{ from: 'GCC', to: 'CLB Nhà Sáng Tạo Game' }, { from: 'ProPTIT', to: 'CLB Lập Trình PTIT' }],
      answer: 'Hai CLB tuyển thành viên theo quy trình khác nhau về số vòng, hình thức và thời điểm.[1][3]',
      table: {
        cols: [{ label: 'ProPTIT', club: 'ProPTIT' }, { label: 'GCC', club: 'GCC' }],
        rows: [
          { k: 'Số vòng', cells: [{ t: '2 vòng', n: 2 }, { t: '3 vòng', n: 4 }] },
          { k: 'Hình thức', cells: [{ t: 'Bài kiểm tra và phỏng vấn', n: 2 }, { t: 'Thử thách làm game nhỏ', n: 4 }] },
          { k: 'Thời điểm', cells: [{ t: 'Đầu học kỳ I', n: 1 }, { t: 'Đầu học kỳ I và II', n: 3 }] }
        ]
      },
      citations: [
        C(1, 21, 'ProPTIT', 'Tuyển thành viên', '[Dữ liệu giả] ProPTIT mở đơn tuyển thành viên vào «đầu học kỳ I» và nhận hồ sơ trực tuyến cho sinh viên năm nhất.', 0.9),
        C(2, 24, 'ProPTIT', 'Quy trình', '[Dữ liệu giả] Quy trình gồm «2 vòng»: bài kiểm tra tư duy lập trình và buổi phỏng vấn với các anh chị trong ban chủ nhiệm.', 0.86),
        C(3, 88, 'GCC', 'Tuyển thành viên', '[Dữ liệu giả] GCC tuyển thành viên vào «đầu học kỳ I và II», ưu tiên những bạn yêu thích làm game.', 0.84),
        C(4, 91, 'GCC', 'Quy trình', '[Dữ liệu giả] Ứng viên trải qua «3 vòng», trong đó có thử thách làm một trò chơi nhỏ theo nhóm.', 0.8),
        C(5, 1, 'S2B', 'Giới thiệu', '[Dữ liệu giả] S2B tổng hợp thông tin tuyển thành viên của ba câu lạc bộ để sinh viên so sánh.', 0.58)
      ],
      stages: [760, 52, 610, 700], llm: 2, tokens: { 'in': 2410, out: 142 }, cost: 0.0029, cache: false, latency: 2122
    },
    rounds: {
      q: 'Muốn vào CLB Multimedia cần qua mấy vòng?', filter: 'Multimedia',
      rewritten: 'CLB Multimedia PTIT có bao nhiêu vòng tuyển thành viên?', expansions: [],
      answer: 'Quy trình tuyển thành viên của CLB Multimedia gồm 3 vòng: xét hồ sơ, bài kiểm tra kỹ năng và phỏng vấn.[1]',
      citations: [
        C(1, 52, 'Multimedia', 'Quy trình', '[Dữ liệu giả] Quy trình tuyển thành viên gồm «3 vòng»: xét hồ sơ, bài kiểm tra kỹ năng và phỏng vấn trực tiếp.', 0.92),
        C(2, 47, 'Multimedia', 'Tuyển thành viên', '[Dữ liệu giả] Ứng viên nộp hồ sơ trực tuyến trong thời gian mở đơn của CLB.', 0.7)
      ],
      stages: [540, 36, 480, 520], llm: 2, tokens: { 'in': 1500, out: 70 }, cost: 0.0017, cache: true, latency: 1576
    },
    gccban: {
      q: 'GCC có những ban nào?', filter: 'GCC',
      rewritten: 'CLB Nhà Sáng Tạo Game (GCC) có những ban nào?', expansions: [{ from: 'GCC', to: 'CLB Nhà Sáng Tạo Game' }],
      answer: 'GCC chia thành các ban Lập trình, Thiết kế đồ họa và Âm thanh – Kịch bản.[1] Mỗi ban phụ trách một phần trong quá trình làm game của CLB.[2]',
      citations: [
        C(1, 90, 'GCC', 'Cơ cấu', '[Dữ liệu giả] CLB gồm các ban «Lập trình», «Thiết kế đồ họa» và «Âm thanh – Kịch bản», do ban chủ nhiệm điều phối.', 0.9),
        C(2, 93, 'GCC', 'Hoạt động', '[Dữ liệu giả] Mỗi ban phụ trách một phần trong quá trình làm game, từ ý tưởng đến phát hành bản thử.', 0.75)
      ],
      stages: [480, 34, 450, 510], llm: 2, tokens: { 'in': 1380, out: 74 }, cost: 0.0016, cache: false, latency: 1474
    },
    s2b: {
      q: 'S2B gồm những câu lạc bộ nào?', filter: null,
      rewritten: 'Cộng đồng S2B gồm những câu lạc bộ nào?', expansions: [],
      answer: 'S2B gồm ba câu lạc bộ: CLB Lập Trình PTIT (ProPTIT), CLB Multimedia PTIT và CLB Nhà Sáng Tạo Game (GCC).[1]',
      citations: [
        C(1, 1, 'S2B', 'Giới thiệu', '[Dữ liệu giả] S2B là cộng đồng sinh viên gồm «ba câu lạc bộ»: ProPTIT, Multimedia và GCC.', 0.94),
        C(2, 2, 'S2B', 'Liên hệ', '[Dữ liệu giả] Sinh viên có thể liên hệ S2B qua trang thông tin chung để được hướng dẫn chọn CLB.', 0.6)
      ],
      stages: [430, 30, 420, 470], llm: 2, tokens: { 'in': 1210, out: 62 }, cost: 0.0014, cache: true, latency: 1350
    },
    long: {
      q: 'Giới thiệu chi tiết về các hoạt động của S2B', filter: null,
      rewritten: 'Giới thiệu chi tiết các hoạt động của cộng đồng S2B', expansions: [],
      answer: 'S2B là cộng đồng gồm ba câu lạc bộ cùng hoạt động trong Học viện.[1] ProPTIT tập trung vào lập trình và đào tạo kỹ năng nền tảng cho thành viên mới.[2] Multimedia hoạt động ở mảng thiết kế, hình ảnh và truyền thông.[3] GCC xoay quanh việc phát triển game theo nhóm nhỏ. Mỗi CLB có các ban chuyên môn riêng, tổ chức buổi sinh hoạt định kỳ và các dự án thực tế. Thành viên mới thường bắt đầu bằng một khóa làm quen, sau đó tham gia ban phù hợp với sở thích. Ngoài ra, ba CLB còn phối hợp tổ chức sự kiện chung vào đầu năm học để giới thiệu với tân sinh viên. Thông tin chi tiết từng đợt được đăng trên kênh chính thức của từng CLB.[1] Toàn bộ nội dung trên là dữ liệu giả để minh họa câu trả lời dài.',
      citations: [
        C(1, 1, 'S2B', 'Giới thiệu', '[Dữ liệu giả] S2B là cộng đồng sinh viên gồm ba câu lạc bộ cùng hoạt động trong «Học viện».', 0.88),
        C(2, 13, 'ProPTIT', 'Hoạt động', '[Dữ liệu giả] ProPTIT tập trung vào «lập trình» và đào tạo kỹ năng nền tảng.', 0.8),
        C(3, 60, 'Multimedia', 'Hoạt động', '[Dữ liệu giả] Multimedia hoạt động ở mảng «thiết kế», hình ảnh và truyền thông.', 0.77)
      ],
      stages: [640, 44, 560, 880], llm: 2, tokens: { 'in': 2100, out: 240 }, cost: 0.0031, cache: false, latency: 2124
    },
    generic: {
      q: '', filter: null, rewritten: '', expansions: [],
      answer: 'Theo tài liệu, nội dung này được mô tả cùng các hoạt động chính của câu lạc bộ.[1] Đây là câu trả lời minh họa (dữ liệu giả).[2]',
      citations: [
        C(1, 14, 'ProPTIT', 'Hoạt động', '[Dữ liệu giả] Đoạn tài liệu mô tả các hoạt động chính, cách tổ chức «ban chuyên môn» và lịch sinh hoạt của CLB.', 0.85),
        C(2, 1, 'S2B', 'Giới thiệu', '[Dữ liệu giả] S2B giới thiệu chung về ba câu lạc bộ dành cho sinh viên.', 0.62)
      ],
      stages: [520, 40, 470, 540], llm: 2, tokens: { 'in': 1450, out: 80 }, cost: 0.0018, cache: false, latency: 1570
    },
    abstain: {
      q: '', filter: null, rewritten: '', expansions: [], abstained: true, answer: '',
      citations: [
        C(1, 30, 'ProPTIT', 'Tuyển thành viên 2026', '[Dữ liệu giả] Tài liệu chỉ có thông tin về «đợt tuyển thành viên năm 2026», không có đợt tuyển các năm trước.', 0.41),
        C(2, 47, 'Multimedia', 'Tuyển thành viên', '[Dữ liệu giả] Đợt tuyển của CLB Multimedia mở đơn vào tháng 9, theo thông báo của năm hiện tại.', 0.37)
      ],
      stages: [610, 40, 500, 330], llm: 2, tokens: { 'in': 1620, out: 40 }, cost: 0.0016, cache: false, latency: 1480
    }
  };
  var ABSTAIN_Q = 'Đợt tuyển thành viên năm 2025 của ProPTIT mở khi nào?';

  var TOPICS = {
    ProPTIT: ['Lịch sử', 'Tuyển thành viên', 'Ban chuyên môn', 'Hoạt động', 'Quy trình', 'Sự kiện', 'Liên hệ'],
    Multimedia: ['Lịch sử', 'Tuyển thành viên', 'Quy trình', 'Sản phẩm', 'Hoạt động', 'Sự kiện'],
    GCC: ['Cơ cấu', 'Tuyển thành viên', 'Quy trình', 'Dự án game', 'Hoạt động'],
    S2B: ['Giới thiệu', 'Thông báo', 'Liên hệ']
  };

  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(seed) { var a = seed >>> 0; return function () { a = (a + 0x6D2B79F5) | 0; var t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

  function seg(answer) {
    var out = [], re = /\[(\d+)\]/g, last = 0, m;
    while ((m = re.exec(answer))) {
      if (m.index > last) out.push({ t: 'text', s: answer.slice(last, m.index) });
      out.push({ t: 'cite', n: +m[1] });
      last = m.index + m[0].length;
    }
    if (last < answer.length) out.push({ t: 'text', s: answer.slice(last) });
    return out;
  }
  function plain(t) { return String(t).replace(/[«»]/g, ''); }
  function hlSegs(t) {
    var out = [], re = /«([^»]+)»/g, last = 0, m;
    while ((m = re.exec(t))) {
      if (m.index > last) out.push({ s: t.slice(last, m.index), h: false });
      out.push({ s: m[1], h: true }); last = m.index + m[0].length;
    }
    if (last < t.length) out.push({ s: t.slice(last), h: false });
    return out;
  }

  /* 20 ứng viên; bm25/dense/rerank là HẠNG (1 = tốt nhất, null = không có trong danh sách) */
  function candidates(sc) {
    var r = rng(hash(sc.key + '|' + sc.query)), used = {}, out = [], names = ['ProPTIT', 'Multimedia', 'GCC', 'S2B'];
    var cited = !sc.abstained;
    sc.citations.forEach(function (c, i) {
      used[c.id] = 1;
      out.push({ id: c.id, club: c.club, topic: c.topic, bm25: 1 + Math.floor(r() * 6), dense: 1 + Math.floor(r() * 6), rerank: i + 1, selected: true, cited: cited });
    });
    var focus = sc.citations.map(function (c) { return c.club; });
    while (out.length < 20) {
      var i = out.length, id; do { id = 1 + Math.floor(r() * 118); } while (used[id]); used[id] = 1;
      var cl = r() < 0.6 ? focus[Math.floor(r() * focus.length)] : names[Math.floor(r() * names.length)];
      var tp = TOPICS[cl][Math.floor(r() * TOPICS[cl].length)];
      var near = i < 5;
      out.push({ id: id, club: cl, topic: tp, bm25: (i >= 14 && r() < 0.25) ? null : (near ? 1 + Math.floor(r() * 8) : 6 + Math.floor(r() * 15)), dense: (i >= 12 && r() < 0.35) ? null : (near ? 1 + Math.floor(r() * 8) : 6 + Math.floor(r() * 15)), rerank: i + 1, selected: near, cited: false });
    }
    return out;
  }

  function scenario(key, query, filter) {
    var base = SC[key] || SC.generic;
    var sc = JSON.parse(JSON.stringify(base));
    sc.key = key;
    if (key === 'abstain') { sc.query = query || ABSTAIN_Q; sc.rewritten = 'Thời điểm mở đợt tuyển thành viên ' + (/\b(\d{4})\b/.exec(sc.query) || ['', 'trước'])[1] + ' của CLB'; }
    else if (key === 'generic') { sc.query = query; sc.rewritten = query; }
    else sc.query = query || base.q;
    sc.original = sc.query;
    sc.userFilter = filter || null;
    sc.inferredFilter = base.filter || null;
    sc.segments = seg(sc.answer || '');
    sc.textLen = sc.segments.reduce(function (a, g) { return a + (g.t === 'text' ? g.s.length : 0); }, 0);
    sc.abstained = !!base.abstained;
    sc.citations.forEach(function (c) { c.plain = plain(c.text); c.hl = hlSegs(c.text); });
    sc.candidates = candidates(sc);
    var cum = 0; sc.stageList = ['rewrite', 'retrieve', 'rerank', 'generate'].map(function (n, i) { var o = { name: n, ms: base.stages[i], start: cum }; cum += base.stages[i]; return o; });
    sc.sumMs = cum;
    sc.plainAnswer = plain(sc.answer.replace(/\[\d+\]/g, ''));
    return sc;
  }

  function route(q) {
    var n = norm(q);
    if (/429|qua tai/.test(n)) return 'err429';
    if (/\bdpt\b|tuyen thanh vien thang may/.test(n)) return 'nodau';
    if (/so sanh/.test(n)) return 'compare';
    if (/thanh lap/.test(n)) return 'founding';
    if (/vong/.test(n) && /multimedia|mm/.test(n)) return 'rounds';
    if (/gcc/.test(n) && /\bban\b/.test(n)) return 'gccban';
    if (/s2b gom|nhung (clb|cau lac bo)/.test(n)) return 's2b';
    if (/chi tiet/.test(n)) return 'long';
    return 'abstain';
  }

  /* ---------- JSON hợp đồng dữ liệu ---------- */
  function contract(sc) {
    var hits = sc.cache ? sc.llm : 0;
    return {
      answer: sc.abstained ? '' : sc.answer,
      abstained: sc.abstained,
      citations: sc.citations.map(function (c) { return { n: c.n, id: c.id, club: c.club, topic: c.topic, text: c.plain, score: +(c.score * 0.0328).toFixed(4), cited: !sc.abstained }; }),
      retrieved_ids: sc.citations.map(function (c) { return c.id; }),
      trace: {
        original_query: sc.original, rewritten_query: sc.rewritten, expansions: sc.expansions,
        clubs: sc.inferredFilter ? [sc.inferredFilter] : [],
        candidates: sc.candidates,
        stages: sc.stageList.map(function (s) { return { name: s.name, ms: s.ms }; }),
        llm_calls: sc.llm, llm_cache_hits: hits, tokens: { 'in': sc.tokens['in'], out: sc.tokens.out, estimated: true }, cost_usd: sc.cost, incidents: []
      },
      latency_ms: sc.latency
    };
  }
  function lines(o, ind) {
    var pad = new Array(ind + 1).join('  ');
    if (Array.isArray(o)) {
      if (!o.length) return ['[]'];
      if (o.every(function (x) { return x && typeof x === 'object'; })) {
        var rows = ['['];
        o.forEach(function (x, i) { rows.push(pad + '  ' + JSON.stringify(x) + (i < o.length - 1 ? ',' : '')); });
        rows.push(pad + ']'); return rows;
      }
      return [JSON.stringify(o)];
    }
    if (o && typeof o === 'object') {
      var ks = Object.keys(o), out = ['{'];
      ks.forEach(function (k, i) {
        var sub = lines(o[k], ind + 1);
        sub[0] = pad + '  ' + JSON.stringify(k) + ': ' + sub[0];
        if (i < ks.length - 1) sub[sub.length - 1] += ',';
        out = out.concat(sub);
      });
      out.push(pad + '}'); return out;
    }
    return [JSON.stringify(o)];
  }
  function jsonText(sc) { return lines(contract(sc), 0).join('\n'); }
  function tokenize(line) {
    var re = /("(?:\\.|[^"\\])*")(\s*:)?|(-?\d+\.?\d*(?:[eE][+-]?\d+)?)|\b(true|false|null)\b|([{}\[\],:])|(\s+)|([^\s])/g, out = [], m;
    while ((m = re.exec(line))) {
      if (m[1] !== undefined) { if (m[2]) { out.push({ t: m[1], cls: 'tk-key' }); out.push({ t: m[2], cls: 'tk-pun' }); } else out.push({ t: m[1], cls: 'tk-str' }); }
      else if (m[3] !== undefined) out.push({ t: m[3], cls: 'tk-num' });
      else if (m[4] !== undefined) out.push({ t: m[4], cls: 'tk-bool' });
      else out.push({ t: m[0], cls: 'tk-pun' });
    }
    return out;
  }
  function jsonLines(sc) { return jsonText(sc).split('\n').map(function (l) { return { toks: tokenize(l) }; }); }

  function grp(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0'); }
  function ms(n) { return grp(n) + ' ms'; }
  function sec(n) { return (n / 1000).toFixed(2).replace('.', ',') + ' s'; }

  var SUGGEST = [
    { id: 's1', club: 'ProPTIT', badge: 'ProPTIT', q: 'CLB Lập Trình PTIT thành lập khi nào?', scene: 'founding', clubs: ['ProPTIT'], base: true },
    { id: 's2', club: 'Multimedia', badge: 'Multimedia', q: 'Muốn vào CLB Multimedia cần qua mấy vòng?', scene: 'rounds', clubs: ['Multimedia'], base: true },
    { id: 's3', club: 'GCC', badge: 'GCC', q: 'GCC có những ban nào?', scene: 'gccban', clubs: ['GCC'], base: true },
    { id: 's4', club: 'cmp', badge: 'So sánh', q: 'So sánh cách tuyển thành viên của ProPTIT và GCC', scene: 'compare', clubs: ['ProPTIT', 'GCC'], base: true },
    { id: 's5', club: 'nodau', badge: 'Không dấu', q: 'clb dpt tuyen thanh vien thang may', scene: 'nodau', clubs: ['Multimedia'], base: true },
    { id: 's6', club: 'S2B', badge: 'S2B', q: 'S2B gồm những câu lạc bộ nào?', scene: 's2b', clubs: [], base: true },
    { id: 'x1', club: 'ProPTIT', badge: 'ProPTIT', q: 'ProPTIT có những ban chuyên môn nào?', scene: 'generic', clubs: ['ProPTIT'] },
    { id: 'x2', club: 'ProPTIT', badge: 'ProPTIT', q: 'Thành viên mới ProPTIT được học những gì?', scene: 'generic', clubs: ['ProPTIT'] },
    { id: 'x3', club: 'Multimedia', badge: 'Multimedia', q: 'CLB Multimedia có những ban nào?', scene: 'generic', clubs: ['Multimedia'] },
    { id: 'x4', club: 'GCC', badge: 'GCC', q: 'GCC thường làm những dự án game nào?', scene: 'generic', clubs: ['GCC'] },
    { id: 'x5', club: 'GCC', badge: 'GCC', q: 'Cách tuyển thành viên của GCC như thế nào?', scene: 'generic', clubs: ['GCC'] }
  ];

  window.S2B = {
    CLUBS: CLUBS, club: club, norm: norm, ICON: ICON, STEPS: STEPS, SUGGEST: SUGGEST, ABSTAIN_Q: ABSTAIN_Q,
    scenario: scenario, route: route, contract: contract, jsonLines: jsonLines, jsonText: jsonText,
    ms: ms, sec: sec, grp: grp, hlSegs: hlSegs, plain: plain
  };
})();

# Report đối chiếu roster & dữ liệu vào trận theo mode (bbb-1qp) + đề xuất UI (bbb-n6m)

Run do user chơi 2026-11-22 trên account pmain (Espada 51921435), capture thụ động
`.tmp/battle_research/events-pmain-20261122-192435.jsonl` (hook broad, 570 event).
Trận đánh: campaign lv316 (`6b02df54`), U Đô lv11201 (`6b02dffb`), Đêm Đỏ lv1039 guest
(`6b02e0bb`). **Tranh Bá (42) đã bị gỡ khỏi game** — không capture được, chỉ suy luận từ
campaign/U Đô (user chốt hướng này). Account mạnh hơn lần capture cũ → số liệu không đối
chiếu chéo được với file cũ, chỉ so trong cùng file này.

## 1. Ánh xạ mode → battleType → signal vào trận

| Mode | battleType | Signal vào trận | Bằng chứng |
|---|---|---|---|
| Campaign | 3 | `ClimbTower`(30) → `发送 EnterRoom(1)` `{battleType:3, level, formationId:1100, battleVersion, configVersion, mapVersion}` → `EnterRoomR` (addr + authCode) | pre trận 0 |
| U Đô | 21 | `发送 EnterRoom(1)` `{battleType:21, formationId:17000, …}` → `EnterRoomR` kèm `clientCost` (vé 30460001 ×1) | pre trận 1 |
| Đêm Đỏ (guest) | 47 | **KHÔNG có EnterRoom gửi đi** — server push `EnterRoomP(3)` (addr/authCode/battleType 47) khi leader bấm bắt đầu; trước đó `ApplyTeam`(12) → `TeamExpeditionInfoP(31)` → `teamChallengeStateP` | pre trận 2 |
| Tranh Bá | 42 | (mẫu cũ 20261121: `EnterRoom(1)` giống campaign) | suy luận |

StartGameP luôn là sự kiện đầu room socket (hook `onStartGamePPush`); configVersion hiện tại
`sea_66328`, mapVersion `trunk_61543`, battleVersion `2.3.1-2_E64067_P63528_C64067`.

## 2. Payload enter/start so theo mode (account mình)

**Giống nhau tuyệt đối giữa campaign và U Đô:**
- `StartGameP.playerInfos[me]`: cùng 13 nhóm field account-level (antiques, builds, skinInfos,
  summonerInfos, daoists, trainingInfos, specialCode, support, goldenSkinsCount, mounts,
  mountCode, roomCode) — **byte-identical từng field** giữa 2 mode.
- Hero lineup: 3 hero trùng (50000026/50000013/50000003) — `attr`, `skills`, `relic`,
  `artifact`, level, breakThrough, fightCap, derma, avatar* **giống hệt** (diff rỗng).

**Khác nhau (đúng thiết kế formation):** `organs` và `summonCreatures` khác giữa 2 mode —
đây là trang bị theo formationId (1100 campaign: organ 10/6/16; 17000 naval: organ 5/10/7;
pet 10003/10004 khác), không phải khác do mode.

**Chuẩn hoá vào trận (xuất hiện ở MỌI mode):** server ghi `attr[6] = 0` và thêm
`attr[10162] = 0` vào từng hero trong StartGameP — sim đã làm đúng 2 bước này trong
`rosterHero()` (web/battle/hero/roster.js) nên roster cache dùng được ngay.

## 3. Nguồn roster & độ đầy đủ (chuẩn = schema 16 field hero trận)

| Nguồn | Phạm vi | Đầy đủ | Ghi chú |
|---|---|---|---|
| `StartGameP.playerInfos[me].heros` | lineup (5-6 hero) | **16/16 field** | ground truth từng trận |
| Snapshot cache lobby (`HeroRosterSnapshot`, 36 hero) | full roster | 14/16 — thiếu `relic`, `artifact`; `skills` thiếu mã skill-skin `8004…` | attr battle-grade (chỉ thiếu normalize 6/10162) |
| `GetRelicInfoR` (login/natural, 1569B) | full account | **relic theo hero**: `relicList` (code/star/level/exp/uuid) + `wearList` (uuid relic → heroUuid) | 11+ relic đang đeo có chủ |
| `GetArtifactInfoR` (login/natural, 1180B) | full account | **artifact theo hero**: `wearList` (uuid món → heroUuid, 11 món, 11/11 heroUuid nằm trong roster cache) + `artifactList` (entryInfos/tempEntryInfos/lockEntryCodes) | khớp uuid với `artifact.uuid` trong StartGameP |
| `TeamExpeditionInfoP.info.teamInfo.team.members[]` (Đêm Đỏ, 151KB/member) | roster TỪNG member | **16/16 field × 36 hero/member** (cùng shape `refreshMemberInfosR`) + formation đội đầy đủ | nguồn roster Đêm Đỏ MỚI — lần này `refreshMemberInfosR` không xuất hiện |
| `refreshMemberInfosR` | roster team | 16/16 | có thể KHÔNG được gửi (lần này vắng) — không phụ thuộc được |

**Kết luận đủ dữ liệu:** một capture lobby session (đã dùng hook broad) chứa đủ nguyên liệu
lập roster 16/16 cho cả 36 hero: cache attr + `GetRelicInfoR`/`GetArtifactInfoR` wearList
gắn chủ. Điều kiện: 2 response đó phải xuất hiện trong session (xem mục 7).

## 4. Câu hỏi chính: attr đầu trận có giống nhau giữa các mode?

**Có — chứng minh bằng dữ liệu:** campaign vs U Đô, hero trùng lineup: attr/skills/relic/
artifact/level/fightCap identical 100% (chỉ cộng normalize 6/10162 như mọi mode). Server
không bơm buff/điều chỉnh theo mode vào hero data ở 2 mode solo này.

→ **Tranh Bá (42) suy luận cùng nhóm**: cùng luồng `EnterRoom` solo, cùng schema StartGameP,
và replay cũ bt42 đã khớp 1/1 TIER1 — khả năng rất cao dùng cùng attr đầu trận. Xếp loại:
giả thuyết mạnh, chưa kiểm chứng lại trên server hiện tại (mode đã gỡ).

## 5. Đêm Đỏ case guest (tham khảo — không mời được guest, user vào team người khác)

**Phân loại bằng chứng (user chốt 2026-11-22):** capture này ở vị trí **GUEST — chỉ watch
được, hạn chế, chỉ dùng để thấy góc nhìn guest**; capture cũ 20261119 (vị trí master, có
`refreshMemberInfosR`) là **chuẩn tham chiếu Đêm Đỏ**. Chủ đề Đêm Đỏ còn thảo luận tiếp —
user sẽ giải thích business ở các điểm chưa rõ; kết luận dưới đây giữ ở mức dữ liệu từng
góc nhìn, không khép lại.

- **Góc nhìn guest (capture này):** team = leader OLLOFI 51456219 (fightCap 5.58M) + Espada
  (guest, 23.6M). `info.teamInfo.team`: formation đội đầy đủ (organ/hero/pet/daoist/derma +
  equipSkills + `formationPlayerId`/`buildSkinPlayerId`) + `members[]` roster đủ 2 người
  (16/16 field × 36 hero/member).
- **Góc nhìn master (capture cũ 20261119 — chuẩn):** 2 slot StartGameP (51921435 master,
  51729833 guest) nhận **cùng lineup đội 6 hero** (50000001/26/04/30/13/03), uuid từng hero
  thuộc chủ thật xen kẽ 3+3 giữa 2 member (kiểm tra qua refreshMemberInfosR rosters);
  attr 6/6 cặp hero bằng nhau (diff "skills/attr" chỉ là thứ tự key serialize). Tức cấu trúc
  "lineup đội dùng chung, hero thật theo owner" có ở **cả hai góc nhìn**.
- Khác biệt theo vai trò (mở, chờ thảo luận): master view — antiques/mountCode/goldenSkinsCount
  giống nhau giữa 2 slot (giá trị của master); guest view — antiques theo account, guest slot
  mountCode=0 goldenSkinsCount=0 (không ảnh hưởng bt47). So sánh canonical (sort key đệ quy):
  **2 slot GIỐNG HẾT organs/pets/daoists/builds/antiques/skins/summoner/training/special/mounts
  ở cả 2 capture — khác duy nhất `support`** (support hero của từng slot). "Organs khác mỗi
  slot" ghi trước đó chỉ là thứ tự key serialize — đã sửa.
- **Trap/pet/spell KHÔNG bị strip khỏi guest slot**: StartGameP guest vẫn mang đủ
  organs/summonCreatures/daoists, và 2 slot mang **cùng một loadout = inventory của
  formationPlayerId** (20261122: formationPlayerId=51921435 guest → loadout là traps lv47/33/33,
  pets, spells của user; 20261119: loadout 10/lv65/s4, 17/lv52/s3, 15/lv52/s1 + pets 10007/10009/10011
  chỉ tồn tại trong inventory của 51729833 → formation player = 弒神). Business hiểu của user:
  chỉ master được chọn spell/trap/pet vào trận, pool nghi là "combine best của 2 bên" —
  NHƯNG StartGameP phản bác combine-best thuần: pet 10001 leader có lv16/s5, guest có
  lv15/s5, trận mang lv15 (của formation player). Kết luận giữ: loadout = formation player;
  rule chọn ai đặt formation — chờ user giải thích thêm. **Không quan trọng cho sim** (user
  chốt): replay mang nguyên loadout từ StartGameP, còn custom thì sim cho tự do toàn bộ slot.
- **Ops trong trận khớp rule "master thao tác"**: capture master 20261119 — 62 ops TOÀN của
  master (type 4 ×9 tạo trap/pet, type 10 ×16 triệu hồi, type 6/8 ×30 option, wheel, base,
  speed); guest 51729833 gửi **0 op**. Capture guest 20261122 — guest chỉ gửi 4 op phi
  gameplay (type 3 ×2 ra quái, type 13 speed 1.6, type 11 ×1 `{"lifeRatio":10000,"entityId":3100014}`
  — op 11 chưa có trong bảng ops của research.md), và `operations[]` trong QuitRoom **chỉ
  chứa op của mình** → **capture từ góc nhìn guest thiếu ops của master, không replay đủ
  trận được**; replay cần capture từ account master.
- **Thông số hero lúc vào trận (focus chính theo user — guest chỉ xem, pet/trap/spell là
  quyền thao tác của master trong trận):** đối chiếu từng hero lineup với roster của chủ
  trong message đội — attr chỉ lệch 2 normalize toàn cục (`attr[6]=0` + thêm
  `attr[10162]=0` ở StartGameP; sim `rosterHero()` đã làm đúng), các field còn lại khớp:
  - Master view 20261119 (chuẩn): attr 6/6 hero ✓; skills roster ĐỦ cả skill-skin `8004…`
    (bằng mã trận, khác thứ tự key); avatarCodes/avatarChapterCodes giống (key order);
    artifact roster bị hook cũ cắt `<deep>` ở entryInfos nhưng code/uuid/exp/_length khớp —
    hook mới serialize nguyên vẹn nên capture mới không còn lỗi này.
  - Guest view 20261122: attr 6/6 hero ✓ (cùng 2 normalize), relic/artifact/relic-owner
    khớp member roster.
  - ⇒ team roster attr = battle-entry grade; sim replay từ StartGameP chính xác mặc nhiên,
    đường thay hero từ roster đội giữ đúng thông số vào trận. Member roster 36/36 hero đều
    có attr đầy đủ.
- Guest **không chơi** (chỉ đúng cho vai guest): 4 op trong QuitRoom (ready/speed/room),
  2 lần `SetWatchFight`; leader điều khiển; damage report guest = 0. Pet/trap/spell trong
  trận là quyền thao tác của master — guest gần như chỉ xem trận.
- Tác động tới bead dùng 1 roster cho 2 player (bbb-w0t.2/.5/.6): nguồn roster đội xác nhận
  là `TeamExpeditionInfoP…members` (guest view) / `refreshMemberInfosR` (master view — chuẩn
  khi có); lineup trận = formation đội ghép hero thật của từng member. Sim Đêm Đỏ cần
  formation đội + member rosters — cả hai đều có trong message tương ứng từng vai.

## 6. Kết luận tái sử dụng & quy trình capture tối thiểu

**Tái sử dụng: ĐẠT 3/4 mode còn lại (campaign, U Đô, Đêm Đỏ) + Tranh Bá suy luận.**
- 1 capture lobby session/account = đủ cho MỌI mode solo: lineup (16/16) + roster 36 hero
  (attr từ cache, relic/artifact từ 2 wearList) + account-level fields.
- Đêm Đỏ cần thêm dữ liệu ĐỘI: master view = `refreshMemberInfosR` (chuẩn, có ở capture cũ),
  guest view = `TeamExpeditionInfoP` (một message là đủ formation + roster 2 member 16/16).
  Muốn **replay** trận Đêm Đỏ thì capture phải đứng ở account **master** (guest view chỉ ghi
  được 4 op của mình, thiếu toàn bộ ops trap/pet/spell của master); chỉ cần roster đội thì
  vào team ở vai nào cũng đủ.
- Về nhóm capture: chỉ còn **2 nhóm** như giả thuyết ban đầu — (A) capture solo account
  (dùng cho campaign/U Đô/Tranh Bá), (B) capture Đêm Đỏ có dữ liệu team (dù là guest hay
  leader, một lần vào team là có TeamExpeditionInfoP).
- Quy trình tối thiểu: mở capture → đăng nhập lobby → (nên mở 1 lần UI Thánh Khí + Thần Khí
  để đảm bảo 2 response enrichment — xem mục 7) → đánh các mode muốn dùng, Đêm Đỏ chỉ cần
  vào team (không cần đánh trọn vẹn nếu chỉ cần roster đội; cần roster formation đội thì
  đứng ở màn chuẩn bị đội là TeamExpeditionInfoP đã về).

## 7. Phân loại bằng chứng

- **Fact** (trong file này): bảng 1-6, identical attr campaign↔U Đô, shared lineup Đêm Đỏ,
  wearList relic/artifact, members roster 16/16, normalize attr 6/10162, guest không gửi op.
- **Giả thuyết mạnh**: Tranh Bá dùng cùng attr đầu trận (mode đã gỡ — không kiểm chứng được).
- **Chưa kiểm chứng**: (a) `GetRelicInfoR`/`GetArtifactInfoR` có phải login-flow cố định hay
  phụ thuộc UI (session 20261119 broad KHÔNG có, session này có ở idx 30-121 — ngay sau
  login, nghi init module nhưng chưa chắc); (b) skill-skin `8004…` chỉ thấy ở lineup trận,
  chưa tìm thấy nguồn lobby cho hero ngoài trận; (c) guest slot mount/golden về 0 — rule
  server chưa rõ.

## 8. Đề xuất UI setup (bbb-n6m — thiết kế, chưa code)

Dựa trên kết quả trên, UI setup nên tách thành 2 lớp:

1. **Lớp "Roster account" (chọn 1 lần, dùng chung):** một dropdown capture nguồn roster
   riêng khỏi phần trận. Hiển thị: account (Espada 51921435), số hero (36), và **mức đầy đủ
   theo từng nhóm dữ liệu** — attr ✓ 36/36, relic ✓ (từ GetRelicInfoR, N món đang đeo),
   artifact ✓ (GetArtifactInfoR, N món), skill-skin ⚠ chỉ có ở lineup, kèm thời điểm session.
   Nếu thiếu enrichment → cảnh báo "roster mode solo sẽ thiếu Thánh Khí/Thần Khí" thay vì
   im lặng. Một capture account phục vụ mọi mode solo → xoá bước chọn lại theo mode.
2. **Lớp "Trận/Mode":** giữ như hiện tại (chọn capture trận để lấy formation, lineup,
   account-level). Đ-label nguồn từng phần: hero trong trận = "trong trận (đủ)"; hero roster
   = "cache lobby + relic/artifact gắn chủ"; Đêm Đỏ = "roster đội từ TeamExpeditionInfoP".
3. **Đêm Đỏ:** khi capture trận là Đêm Đỏ, hiện formation đội (hero của ai — owner name mỗi
   slot, từ members[]) thay vì giả định 1 player. Guest case: đánh dấu "guest (xem), leader
   OLLOFI điều khiển".
4. **Điều kiện hiển thị:** hero ngoài lineup thiếu skill-skin → chip ⚠ nhỏ ở row hero;
   Tranh Bá hiển thị kèm nhãn "suy luận từ campaign/U Đô (mode đã gỡ)".
5. **Giảm thao tác:** không bắt chọn lại roster cho từng mode; chỉ chuyển capture khi đổi
   account hoặc cần Đêm Đỏ (lớp 2). Case giả thuyết sai (roster không dùng được cho mode
   nào) → nút "Kiểm tra tương thích" chạy thử 1 trận sim rồi báo chênh lệch attr.

# KoMM-VQA

PDF 문서 기반 VQA 데이터셋 생성을 위한 Streamlit 어노테이션 도구.

## 설치

### 1. uv 설치 및 환경 세팅

```bash
# uv 설치 (없는 경우)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 프로젝트 디렉토리에서 의존성 설치
uv sync
```

### 2. PostgreSQL 환경변수 설정

`postgresql/.env` 파일 생성 (`.env.example` 참고):

```bash
cp postgresql/.env.example postgresql/.env
```

`postgresql/.env` 파일 수정:
```env
POSTGRES_DB=kommvqa
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
PG_PORT=5432
```

### 3. Docker로 PostgreSQL 실행

```bash
make docker-up
```

**주의:** `postgresql/pgdata/` 폴더에 모든 데이터베이스 데이터가 저장됩니다. 이 폴더를 삭제하면 모든 데이터가 손실됩니다.

```bash
# 종료
make docker-down

# 로그 확인 (postgresql 폴더에서)
cd postgresql && docker compose logs -f

# 데이터베이스 완전 삭제
make clean-docker
```

### 4. Streamlit 설정

`.streamlit/secrets.toml` 파일 생성:
```toml
[database]
host = "localhost"
port = 5432
database = "kommvqa"
user = "postgres"
password = "your_password"
```

`postgresql/.env`와 동일한 값으로 설정.

### 5. Streamlit 실행

```bash
uv run streamlit run komm_vqa/app/main.py
```

브라우저에서 `http://localhost:8501` 접속.

---

## 사용법

### File Management (📁)

**Upload PDF 탭:**
1. PDF 파일 선택
2. "Process PDF" 클릭
3. 각 페이지가 이미지로 변환되어 DB에 저장됨

=> 제작에 사용하시는 PDF를 여기에 올려주시면 됩니다. data/pdfs 폴더에 저장되고, 추후에 해당 폴더를 압축해서 공유해주시면 됩니다.

**Upload Images 탭:**
1. 여러 이미지 파일 선택 (PNG, JPG, JPEG, WEBP, BMP, TIFF 지원)
2. 이미지들이 파일 이름 순으로 자동 정렬됨
3. Document title 입력 (선택사항)
4. "Create PDF and Process" 클릭
5. 이미지들이 하나의 PDF로 결합되어 저장됨

=> PDF가 없고 이미지들만 있는 경우 이 탭을 사용하세요.

**Browse Documents 탭:**
- 문서 선택 후 PDF Viewer 또는 Page by Number로 확인
- Delete Document로 문서 삭제

### QA Creation (❓)

**1. Select Pages (좌측):**
1. 문서 선택
2. 페이지 번호 입력
3. 미리보기 확인 후 "Add Page" 클릭
4. 필요한 페이지 모두 추가

=> PDF 문서는 직접 컴퓨터에서 열어서 보며 제작하시는 것이 편할 것이고, 해당하는 페이지 번호만 입력해서 확인하고 추가해주시면 됩니다.

**2. Enter Query (우측):**
1. Query 입력 (필수) - 질문 형태로 작성합니다.
2. 객관식 입력 - 질문과 선지를 모두 포함한 형태로 작성합니다. 위에 작성한 Query가 여기에도 포함이 되어있어야 합니다 (LLM에게 들어가는 쿼리+선지 형태라고 생각하시면 됩니다)
3. Generation GT 입력 (필수) - "Add Answer"로 여러 답안 추가 가능합니다. (서술형 정답, 객관식 정답 하나씩 포함하면 좋겠습니다)
4. Relation Type 선택:
   - **AND**: 모든 페이지가 필요 (multi-hop)
   - **OR**: 페이지 중 하나만 있으면 됨
   - **Multi-Hop**은 그냥 AND를 선택해주면 됩니다. 저희의 경우에는 OR는 필요하지 않을 것 같습니다.
5. "Submit Query" → "Confirm and Create" 클릭. **반드시 Confirm and Create를 눌러야 쿼리가 생성됩니다!**

### Data Browser (📊)

**Queries 탭:**
- 생성된 쿼리 목록 확인
- 각 쿼리의 Retrieval GT 이미지 확인
- 쿼리 삭제

**Statistics 탭:**
- 전체 데이터셋 통계 확인

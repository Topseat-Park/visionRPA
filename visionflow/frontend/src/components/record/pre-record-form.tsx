import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { useRecordingStore } from '@/stores/recording-store';

const EXCEPTION_OPTIONS = [
  { id: 'popup', label: '팝업/대화상자' },
  { id: 'login_expired', label: '로그인 만료' },
  { id: 'slow_loading', label: '느린 로딩' },
];

export function PreRecordForm({ onSubmit }: { onSubmit: () => void }) {
  const { preRecordData, setPreRecordData } = useRecordingStore();

  const canSubmit = preRecordData.purpose.trim().length > 0;

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h3 className="text-lg font-semibold">사전 정보 입력</h3>
        <p className="text-sm text-muted-foreground">
          AI가 워크플로우를 이해하는 데 도움이 되는 정보를 입력하세요
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="purpose">
            워크플로우 목적 <span className="text-destructive">*</span>
          </Label>
          <Input
            id="purpose"
            placeholder="예: ERP에서 일일 매출 보고서 다운로드"
            value={preRecordData.purpose}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPreRecordData({ purpose: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="apps">사용 앱/시스템</Label>
          <Input
            id="apps"
            placeholder="예: Chrome, Excel, SAP (쉼표로 구분)"
            value={preRecordData.apps.join(', ')}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setPreRecordData({
                apps: e.target.value
                  .split(',')
                  .map((s: string) => s.trim())
                  .filter(Boolean),
              })
            }
          />
        </div>

        <div className="space-y-3">
          <Label>예외 상황</Label>
          {EXCEPTION_OPTIONS.map((opt) => (
            <div key={opt.id} className="flex items-center gap-2">
              <Checkbox
                id={opt.id}
                checked={preRecordData.exceptions.includes(opt.id)}
                onCheckedChange={(checked: boolean) => {
                  const next = checked
                    ? [...preRecordData.exceptions, opt.id]
                    : preRecordData.exceptions.filter((e: string) => e !== opt.id);
                  setPreRecordData({ exceptions: next });
                }}
              />
              <Label htmlFor={opt.id} className="font-normal">
                {opt.label}
              </Label>
            </div>
          ))}
        </div>

        <div className="space-y-2">
          <Label htmlFor="exception_notes">기타 예외 상황</Label>
          <Textarea
            id="exception_notes"
            placeholder="추가 예외 상황을 설명하세요..."
            value={preRecordData.exception_notes}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
              setPreRecordData({ exception_notes: e.target.value })
            }
            rows={2}
          />
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            id="sensitive"
            checked={preRecordData.has_sensitive_info}
            onCheckedChange={(checked: boolean) =>
              setPreRecordData({ has_sensitive_info: !!checked })
            }
          />
          <Label htmlFor="sensitive" className="font-normal">
            민감 정보 포함 (비밀번호, 개인정보)
          </Label>
        </div>
      </div>

      <Button onClick={onSubmit} disabled={!canSubmit} className="w-full">
        녹화 시작
      </Button>
    </div>
  );
}

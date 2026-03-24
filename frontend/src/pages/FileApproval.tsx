import { useState, useEffect } from 'react';
import { FileText, CheckCircle, XCircle, Clock, Eye } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Textarea } from './ui/textarea';
import { toast } from 'sonner';
import type { UploadedFile } from './FileManagement';

export function FileApproval() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<UploadedFile | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectDialog, setShowRejectDialog] = useState(false);

  useEffect(() => {
    loadFiles();
    
    // الاستماع لتغييرات localStorage من علامات تبويب أخرى
    const handleStorageChange = () => {
      loadFiles();
    };
    
    window.addEventListener('storage', handleStorageChange);
    
    // التحديث كل 5 ثوانٍ للحصول على آخر البيانات
    const interval = setInterval(loadFiles, 5000);
    
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, []);

  const loadFiles = () => {
    const savedFiles = localStorage.getItem('uploadedFiles');
    if (savedFiles) {
      const parsedFiles = JSON.parse(savedFiles);
      const filesWithDates = parsedFiles.map((file: any) => ({
        ...file,
        uploadedAt: new Date(file.uploadedAt)
      }));
      setFiles(filesWithDates);
    }
  };

  const handleApprove = (fileId: string) => {
    const updatedFiles = files.map(f => 
      f.id === fileId ? { ...f, status: 'approved' as const } : f
    );
    setFiles(updatedFiles);
    localStorage.setItem('uploadedFiles', JSON.stringify(updatedFiles));
    
    // إضافة المحتوى إلى قاعدة المعرفة (RAG)
    const approvedFile = updatedFiles.find(f => f.id === fileId);
    if (approvedFile) {
      addToKnowledgeBase(approvedFile);
    }
    
    toast.success('تمت الموافقة على الملف وإضافته إلى قاعدة المعرفة');
    setSelectedFile(null);
  };

  const handleReject = (fileId: string) => {
    if (!rejectionReason.trim()) {
      toast.error('يرجى إدخال سبب الرفض');
      return;
    }

    const updatedFiles = files.map(f => 
      f.id === fileId 
        ? { ...f, status: 'rejected' as const, rejectionReason: rejectionReason } 
        : f
    );
    setFiles(updatedFiles);
    localStorage.setItem('uploadedFiles', JSON.stringify(updatedFiles));
    
    toast.success('تم رفض الملف');
    setShowRejectDialog(false);
    setRejectionReason('');
    setSelectedFile(null);
  };

  const addToKnowledgeBase = (file: UploadedFile) => {
    // إضافة محتوى الملف إلى قاعدة المعرفة
    const knowledgeBase = JSON.parse(localStorage.getItem('knowledgeBase') || '[]');
    
    const newKnowledgeItem = {
      id: `kb_${Date.now()}`,
      source: file.name,
      content: file.content,
      addedAt: new Date().toISOString(),
      fileId: file.id
    };
    
    knowledgeBase.push(newKnowledgeItem);
    localStorage.setItem('knowledgeBase', JSON.stringify(knowledgeBase));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' بايت';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' كيلوبايت';
    return (bytes / (1024 * 1024)).toFixed(1) + ' ميجابايت';
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return (
          <Badge className="bg-green-500 text-white">
            <CheckCircle className="w-3 h-3 ml-1" />
            موافق عليه
          </Badge>
        );
      case 'rejected':
        return (
          <Badge className="bg-red-500 text-white">
            <XCircle className="w-3 h-3 ml-1" />
            مرفوض
          </Badge>
        );
      default:
        return (
          <Badge className="bg-yellow-500 text-white">
            <Clock className="w-3 h-3 ml-1" />
            قيد المراجعة
          </Badge>
        );
    }
  };

  const pendingFiles = files.filter(f => f.status === 'pending');
  const approvedFiles = files.filter(f => f.status === 'approved');
  const rejectedFiles = files.filter(f => f.status === 'rejected');

  const FileCard = ({ file }: { file: UploadedFile }) => (
    <div className="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1">
          <FileText className="w-5 h-5 text-blue-600 mt-1" />
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-medium text-gray-900">{file.name}</h4>
              {getStatusBadge(file.status)}
            </div>
            <div className="text-sm text-gray-500 space-y-1">
              <p>رفع بواسطة: {file.uploadedBy}</p>
              <p>الحجم: {formatFileSize(file.size)}</p>
              <p>التاريخ: {file.uploadedAt.toLocaleDateString('ar-EG', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              })}</p>
              {file.status === 'rejected' && file.rejectionReason && (
                <p className="text-red-600 mt-2">
                  <span className="font-medium">سبب الرفض:</span> {file.rejectionReason}
                </p>
              )}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Eye className="w-4 h-4 ml-1" />
                عرض
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[80vh]" dir="rtl">
              <DialogHeader>
                <DialogTitle>{file.name}</DialogTitle>
                <DialogDescription>
                  معاينة محتوى الملف
                </DialogDescription>
              </DialogHeader>
              <div className="mt-4">
                <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto" dir="rtl">
                  <pre className="whitespace-pre-wrap text-sm font-mono text-right">
                    {file.content.substring(0, 2000)}
                    {file.content.length > 2000 && '\n\n... (تم اقتطاع المحتوى)'}
                  </pre>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          
          {file.status === 'pending' && (
            <>
              <Button
                size="sm"
                onClick={() => handleApprove(file.id)}
                className="bg-green-600 hover:bg-green-700 text-white"
              >
                <CheckCircle className="w-4 h-4 ml-1" />
                موافقة
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => {
                  setSelectedFile(file);
                  setShowRejectDialog(true);
                }}
              >
                <XCircle className="w-4 h-4 ml-1" />
                رفض
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6" dir="rtl">
      <Card>
        <CardHeader>
          <CardTitle>إدارة الملفات المرفوعة</CardTitle>
          <CardDescription>
            مراجعة والموافقة على الملفات المرفوعة من قبل الموظفين
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <Clock className="w-8 h-8 text-yellow-600" />
                <div>
                  <p className="text-2xl font-bold text-yellow-900">{pendingFiles.length}</p>
                  <p className="text-sm text-yellow-700">في انتظار المراجعة</p>
                </div>
              </div>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-8 h-8 text-green-600" />
                <div>
                  <p className="text-2xl font-bold text-green-900">{approvedFiles.length}</p>
                  <p className="text-sm text-green-700">موافق عليها</p>
                </div>
              </div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <XCircle className="w-8 h-8 text-red-600" />
                <div>
                  <p className="text-2xl font-bold text-red-900">{rejectedFiles.length}</p>
                  <p className="text-sm text-red-700">مرفوضة</p>
                </div>
              </div>
            </div>
          </div>

          <Tabs defaultValue="pending" dir="rtl">
            <TabsList className="w-full">
              <TabsTrigger value="pending" className="flex-1">
                قيد المراجعة ({pendingFiles.length})
              </TabsTrigger>
              <TabsTrigger value="approved" className="flex-1">
                موافق عليها ({approvedFiles.length})
              </TabsTrigger>
              <TabsTrigger value="rejected" className="flex-1">
                مرفوضة ({rejectedFiles.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="pending" className="mt-4">
              {pendingFiles.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Clock className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                  <p>لا توجد ملفات في انتظار المراجعة</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {pendingFiles.map(file => (
                    <FileCard key={file.id} file={file} />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="approved" className="mt-4">
              {approvedFiles.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <CheckCircle className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                  <p>لا توجد ملفات موافق عليها</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {approvedFiles.map(file => (
                    <FileCard key={file.id} file={file} />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="rejected" className="mt-4">
              {rejectedFiles.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <XCircle className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                  <p>لا توجد ملفات مرفوضة</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {rejectedFiles.map(file => (
                    <FileCard key={file.id} file={file} />
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* نافذة رفض الملف */}
      <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <DialogContent dir="rtl">
          <DialogHeader>
            <DialogTitle>رفض الملف</DialogTitle>
            <DialogDescription>
              يرجى توضيح سبب رفض الملف "{selectedFile?.name}"
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <Textarea
              placeholder="اكتب سبب الرفض هنا..."
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              rows={4}
              className="text-right"
            />
            <div className="flex gap-3 justify-end">
              <Button
                variant="outline"
                onClick={() => {
                  setShowRejectDialog(false);
                  setRejectionReason('');
                  setSelectedFile(null);
                }}
              >
                إلغاء
              </Button>
              <Button
                variant="destructive"
                onClick={() => selectedFile && handleReject(selectedFile.id)}
              >
                تأكيد الرفض
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

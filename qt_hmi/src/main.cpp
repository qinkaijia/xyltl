#include <QApplication>
#include <QRect>
#include <QRegExp>
#include <QScreen>
#include <QString>
#include <QStringList>

#include "FinalStatusDataProvider.h"
#include "MainWindow.h"
#include "MockDataProvider.h"
#include "StatusModel.h"
#include "SystemStatus.h"

static QString argumentValue(const QStringList &args, const QString &name)
{
    const int index = args.indexOf(name);
    if (index >= 0 && index + 1 < args.size()) {
        return args.at(index + 1);
    }
    return QString();
}

static QRect parseGeometry(const QString &text, bool *ok)
{
    *ok = false;
    QRegExp rx(QStringLiteral("^(\\d+)x(\\d+)([+-]\\d+)?([+-]\\d+)?$"));
    if (!rx.exactMatch(text)) {
        return QRect();
    }
    const int width = rx.cap(1).toInt();
    const int height = rx.cap(2).toInt();
    const int x = rx.cap(3).isEmpty() ? 0 : rx.cap(3).toInt();
    const int y = rx.cap(4).isEmpty() ? 0 : rx.cap(4).toInt();
    *ok = width > 0 && height > 0;
    return QRect(x, y, width, height);
}

static QRect screenGeometry(const QString &screenName)
{
    if (screenName.isEmpty()) {
        QScreen *screen = QApplication::primaryScreen();
        return screen ? screen->availableGeometry() : QRect();
    }
    const QList<QScreen *> screens = QApplication::screens();
    for (QScreen *screen : screens) {
        if (screen && screen->name() == screenName) {
            return screen->availableGeometry();
        }
    }
    return QRect();
}

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    qRegisterMetaType<SystemStatus>("SystemStatus");

    const QStringList args = app.arguments();
    const QString statusFile = argumentValue(args, QStringLiteral("--status-file"));
    const bool compactMode = args.contains(QStringLiteral("--compact"));

    MockDataProvider mockProvider;
    FinalStatusDataProvider finalStatusProvider(statusFile);
    IDataProvider *provider = statusFile.isEmpty()
        ? static_cast<IDataProvider *>(&mockProvider)
        : static_cast<IDataProvider *>(&finalStatusProvider);

    StatusModel model;
    model.setProvider(provider);

    MainWindow window(&model, compactMode);
    const QRect targetScreen = screenGeometry(argumentValue(args, QStringLiteral("--screen")));
    if (targetScreen.isValid()) {
        window.setGeometry(targetScreen);
    }
    bool geometryOk = false;
    const QRect requestedGeometry = parseGeometry(argumentValue(args, QStringLiteral("--geometry")), &geometryOk);
    if (geometryOk) {
        window.setGeometry(requestedGeometry);
    }
    if (args.contains(QStringLiteral("--fullscreen"))) {
        window.showFullScreen();
    } else {
        window.show();
    }

    provider->start();
    return app.exec();
}

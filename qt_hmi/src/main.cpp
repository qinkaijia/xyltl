#include <QApplication>
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

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    qRegisterMetaType<SystemStatus>("SystemStatus");

    const QStringList args = app.arguments();
    const QString statusFile = argumentValue(args, QStringLiteral("--status-file"));

    MockDataProvider mockProvider;
    FinalStatusDataProvider finalStatusProvider(statusFile);
    IDataProvider *provider = statusFile.isEmpty()
        ? static_cast<IDataProvider *>(&mockProvider)
        : static_cast<IDataProvider *>(&finalStatusProvider);

    StatusModel model;
    model.setProvider(provider);

    MainWindow window(&model);
    if (args.contains(QStringLiteral("--fullscreen"))) {
        window.showFullScreen();
    } else {
        window.show();
    }

    provider->start();
    return app.exec();
}

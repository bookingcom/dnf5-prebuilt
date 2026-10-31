// The `lock` command of dnf5: resolves packages into a JSON lockfile.

#ifndef DNF_DNF5_LOCK_HPP
#define DNF_DNF5_LOCK_HPP

#include <dnf5/context.hpp>

#include <string>
#include <vector>

namespace dnf5 {

class LockCommand : public Command {
public:
    explicit LockCommand(Context & context) : Command(context, "lock") {}
    void set_parent_command() override;
    void set_argument_parser() override;
    void configure() override;
    void run() override;

private:
    /// Lockfile to write; standard output when empty.
    std::string output;
    /// Architectures a package may have.
    std::vector<std::string> archlist;
    /// Packages to prune from the dependency tree (dnf5 has a global --exclude of its own, which hides them instead).
    std::vector<std::string> prune;
    std::vector<std::string> module_enable;
    /// Lockfiles of the layers below, in order.
    std::vector<std::string> lockfiles;
    std::vector<std::string> specs;
};

}  // namespace dnf5

#endif  // DNF_DNF5_LOCK_HPP

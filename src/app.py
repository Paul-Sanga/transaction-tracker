import click

from controller import auth, account, category, transaction, investment, snapshot, investment_transaction, goal, contribution, report, vehicle

@click.group()
def main():
    pass

main.add_command(auth)
main.add_command(goal)
main.add_command(report)
main.add_command(vehicle)
main.add_command(account)
main.add_command(category)
main.add_command(snapshot)
main.add_command(investment)
main.add_command(transaction)
main.add_command(contribution)
main.add_command(investment_transaction)


if __name__ == "__main__":
    main()